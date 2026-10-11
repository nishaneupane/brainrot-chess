"""Build report.html from runs/latest.json (or a run file passed as an argument).

Everything here is encoding-safe by construction: files are read and written as
explicit UTF-8 (never the machine's locale encoding), and the page itself comes
out pure ASCII, so it renders the same whether it is opened from disk on Windows,
served by a host that guesses latin-1, or emailed around.
"""
import json
import re
import sys
from pathlib import Path

TEMPLATE = Path(__file__).with_name("report_template.html")

# Emoji survive JSON fine but not every device has a font for them, so the LLM's
# decorations are stripped rather than shipped as tofu boxes.
EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200D]")


def load(src):
    return json.loads(Path(src).read_text(encoding="utf-8"))


class StaleRun(Exception):
    """A run file written by an older version of the league."""


def build_payload(data, live=False):
    agents, gens = data["agents"], data["generations"]
    if not gens or not agents:
        raise StaleRun("That run file has no generations in it. Re-run `python evolve.py`.")
    if "style" not in next(iter(agents.values())):
        raise StaleRun("That run file predates the style/playbook rename, so the report cannot be "
                       "built from it. Re-run `python evolve.py` to get a current one.")
    final = gens[-1]
    names = {k: v["name"] for k, v in agents.items()} | {"npc": "NPC Bot"}

    def lineage(aid):
        chain = []
        while aid in agents and len(chain) < 40:
            a = agents[aid]
            chain.append({"name": a["name"], "gen": a["generation"], "style": a["style"],
                          "playbook": a["playbook"]})
            aid = a["parents"][0] if a["parents"] else None
        return chain

    def replay(r, label):
        if not r:
            return None
        return {"label": label, "white": names.get(r["white"]), "black": names.get(r["black"]),
                "winner": names.get(r["winner"]) if r["winner"] else None, "how": r["how"],
                "fens": r["fens"], "sans": r["moves"], "comments": r["comments"]}

    payload = {
        "run": data["run_id"],
        "live": live,
        "gens": [{"g": g["generation"], "avg": g["avg_vs_npc"], "best": g["best_vs_npc"]} for g in gens],
        "board": [s | {"style": agents[s["id"]]["style"], "playbook": agents[s["id"]]["playbook"],
                       "gen": agents[s["id"]]["generation"]} for s in final["standings"]],
        "lineage": lineage(final["champion"]),
        "deaths": sum(len(g["standings"]) // 2 for g in gens[:-1]),
        "games": len(data["matches"]),
        "replays": [x for x in (replay(data.get("replay_before"), "Before: weakest gen 0 bot"),
                                replay(data.get("replay_after"), f"After: gen {final['generation']} champion")) if x],
    }
    return json.loads(re.sub(r" ?" + EMOJI.pattern, "", json.dumps(payload, ensure_ascii=False)))


def render(payload):
    """Template + data -> one self-contained ASCII-only HTML document."""
    html = TEMPLATE.read_text(encoding="utf-8")
    # ensure_ascii escapes every non-ASCII character in the data as \uXXXX, and the
    # template is ASCII already, so the result is byte-identical under any charset.
    html = html.replace("/*DATA*/null", json.dumps(payload))
    return html.encode("ascii", "backslashreplace").decode("ascii")


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "runs/latest.json"
    out = Path("report.html")
    out.write_text(render(build_payload(load(src))), encoding="utf-8", newline="\n")
    print(f"Wrote {out.resolve()}")
    print("Tip: `python serve.py` for the interactive version (play the bots yourself).")


if __name__ == "__main__":
    main()
