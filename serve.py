"""Localhost server for the Brainrot Chess League.

  python serve.py                 # http://127.0.0.1:8000
  python serve.py --port 5000 --run runs/run-20261011-152355.json

Serves the league report at / (re-read from disk on every request, so re-running
evolve.py just needs a refresh) and a small JSON API behind /api/ that lets you
play a real game against any bot the league ever bred. No extra dependencies:
stdlib http.server plus python-chess, which the league already needs.
"""
import argparse
import json
import re
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import chess

import report
from agents import Agent
from game import MAX_PLIES, NPCBot, commentary, outcome

MAX_SESSIONS = 200  # one in-memory board per visitor tab; oldest are evicted

# commentary() is written about a third party ("Rizzler Rook captures a rook"), so the
# handful of verbs it uses get conjugated when the mover is the person playing.
VOICE = {"castles": "castle", "captures": "capture", "moves": "move", "wins": "win"}


def human_voice(text):
    return re.sub(r"\bYou (%s)\b" % "|".join(VOICE), lambda m: "You " + VOICE[m[1]], text)


class League:
    """The bred bots, loaded from a run file, as opponents you can actually play."""

    def __init__(self, run_path):
        self.run_path = Path(run_path)
        self.games = {}
        self.lock = threading.Lock()

    def data(self):
        return report.load(self.run_path)

    def page(self):
        return report.render(report.build_payload(self.data(), live=True))

    def roster(self):
        data = self.data()
        rank = {s["id"]: i for i, s in enumerate(data["generations"][-1]["standings"])}
        champs = {g["champion"] for g in data["generations"]}
        bots = [{"id": a["id"], "name": a["name"], "gen": a["generation"], "style": a["style"],
                 "playbook": a["playbook"], "champion": a["id"] in champs,
                 "rank": rank.get(a["id"])} for a in data["agents"].values()]
        # still-standing bots first in league order, then eliminated ones newest-first
        bots.sort(key=lambda b: (b["rank"] is None, b["rank"] if b["rank"] is not None else -b["gen"],
                                 b["name"]))
        return [{"id": "npc", "name": "NPC Bot", "gen": None, "style": "The baseline nobody respects",
                 "playbook": "Takes a free mate or the biggest capture, otherwise plays at random.",
                 "champion": False, "rank": None}] + bots

    def opponent(self, oid):
        if oid == "npc":
            return NPCBot()
        a = self.data()["agents"].get(oid)
        if not a:
            return None
        return Agent(a["genes"], a["name"], a["style"], a["generation"], a["parents"],
                     a["playbook"], a["id"])

    def new_game(self, oid, human_white):
        bot = self.opponent(oid)
        if bot is None:
            return None
        gid = uuid.uuid4().hex[:12]
        g = {"board": chess.Board(), "bot": bot, "human_white": human_white,
             "feed": [], "last": None, "born": time.time(), "lock": threading.Lock()}
        with self.lock:
            if len(self.games) >= MAX_SESSIONS:
                for old in sorted(self.games, key=lambda k: self.games[k]["born"])[:MAX_SESSIONS // 4]:
                    self.games.pop(old, None)
            self.games[gid] = g
        if not human_white:
            self.bot_move(g)
        return gid, g

    def bot_move(self, g):
        board = g["board"]
        if board.is_game_over(claim_draw=True) or len(board.move_stack) >= MAX_PLIES:
            return
        move = g["bot"].choose(board)
        self.push(g, move, g["bot"].name)

    def push(self, g, move, who, human=False):
        board = g["board"]
        white = board.turn == chess.WHITE
        num = f"{board.fullmove_number}{'.' if white else '...'}"
        san, note = board.san(move), commentary(board, move, who)
        board.push(move)
        g["last"] = [chess.square_name(move.from_square), chess.square_name(move.to_square)]
        g["feed"].insert(0, {"n": num, "san": san, "who": who,
                             "text": human_voice(note) if human else note})

    def state(self, gid, g):
        board, human_white = g["board"], g["human_white"]
        human_turn = board.turn == (chess.WHITE if human_white else chess.BLACK)
        capped = len(board.move_stack) >= MAX_PLIES
        over = board.is_game_over(claim_draw=True) or capped
        moves = {}
        if not over and human_turn:
            for m in board.legal_moves:
                moves.setdefault(chess.square_name(m.from_square), []).append(m.uci())
        verdict = None
        if over:
            result, how = outcome(board)
            you = 0 if human_white else 1
            verdict = {"how": how,
                       "winner": "you" if result == you else ("draw" if result is None else "bot")}
        return {"game": gid, "fen": board.board_fen(), "you": "white" if human_white else "black",
                "bot": g["bot"].name, "moves": moves, "over": over, "verdict": verdict,
                "check": board.is_check(), "your_turn": human_turn and not over,
                "ply": len(board.move_stack), "cap": MAX_PLIES, "last": g["last"],
                "feed": g["feed"][:40]}

    def move(self, gid, uci):
        with self.lock:
            g = self.games.get(gid)
        if not g:
            return None, "That game is gone (the server restarted). Start a new one."
        with g["lock"]:
            return self._move(g, gid, uci)

    def _move(self, g, gid, uci):
        board = g["board"]
        if board.is_game_over(claim_draw=True) or len(board.move_stack) >= MAX_PLIES:
            return self.state(gid, g), None
        if board.turn != (chess.WHITE if g["human_white"] else chess.BLACK):
            return self.state(gid, g), None
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            return None, "Not a move."
        if move not in board.legal_moves:
            return None, "Illegal move."
        self.push(g, move, "You", human=True)
        self.bot_move(g)
        return self.state(gid, g), None


class Handler(BaseHTTPRequestHandler):
    server_version = "BrainrotChess/1.0"
    league = None

    def log_message(self, fmt, *args):  # one tidy line instead of two
        print(f"  {self.command} {self.path} -> {args[1] if len(args) > 1 else ''}")

    def send(self, code, body, ctype):
        # Everything goes out as UTF-8 and says so, on the wire and in the markup.
        blob = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Content-Length", str(len(blob)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(blob)

    def json(self, code, obj):
        self.send(code, json.dumps(obj, ensure_ascii=True), "application/json")

    def body(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(n) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return {}

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/") or "/"
        try:
            if path == "/":
                return self.send(200, self.league.page(), "text/html")
            if path == "/api/roster":
                return self.json(200, {"roster": self.league.roster()})
            if path == "/api/health":
                return self.json(200, {"ok": True, "run": self.league.data()["run_id"]})
        except FileNotFoundError:
            return self.send(404, "No run found. Run `python evolve.py` first.", "text/plain")
        except (report.StaleRun, ValueError) as e:
            return self.send(500, str(e), "text/plain")
        self.json(404, {"error": "no such endpoint"})

    do_HEAD = do_GET

    def do_POST(self):
        path = self.path.split("?")[0].rstrip("/")
        b = self.body()
        if path == "/api/new":
            made = self.league.new_game(str(b.get("opponent", "npc")), b.get("color") != "black")
            if not made:
                return self.json(404, {"error": "No such bot."})
            gid, g = made
            return self.json(200, self.league.state(gid, g))
        if path == "/api/move":
            state, err = self.league.move(str(b.get("game", "")), str(b.get("uci", "")))
            return self.json(200, state) if state else self.json(400, {"error": err})
        self.json(404, {"error": "no such endpoint"})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--run", default="runs/latest.json")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    run = Path(args.run)
    if not run.exists():
        raise SystemExit(f"{run} not found. Run `python evolve.py` first.")
    Handler.league = League(run)

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}"
    print(f"Brainrot Chess League live at {url}")
    print(f"  run file: {run}  (edit/re-run evolve.py and just refresh)")
    print("  Ctrl+C to stop\n")
    if not args.no_browser:
        threading.Timer(0.6, webbrowser.open, [url]).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
