"""Build report.html from runs/latest.json (or a run file passed as an argument)."""
import json
import re
import sys
from pathlib import Path

src = Path(sys.argv[1] if len(sys.argv) > 1 else "runs/latest.json")
data = json.loads(src.read_text())
agents, gens = data["agents"], data["generations"]
final = gens[-1]
names = {k: v["name"] for k, v in agents.items()} | {"npc": "NPC Bot"}


def lineage(aid):
    chain = []
    while aid in agents and len(chain) < 40:
        a = agents[aid]
        chain.append({"name": a["name"], "gen": a["generation"], "personality": a["personality"],
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
    "gens": [{"g": g["generation"], "avg": g["avg_vs_npc"], "best": g["best_vs_npc"]} for g in gens],
    "board": [s | {"personality": agents[s["id"]]["personality"], "trash": agents[s["id"]]["trash_talk"],
                   "gen": agents[s["id"]]["generation"]} for s in final["standings"]],
    "lineage": lineage(final["champion"]),
    "deaths": sum(len(g["standings"]) // 2 for g in gens[:-1]),
    "games": len(data["matches"]),
    "replays": [x for x in (replay(data.get("replay_before"), "Gen 0 clown"),
                            replay(data.get("replay_after"), f"Gen {final['generation']} champ")) if x],
}

EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200D]")
payload = json.loads(re.sub(r" ?" + EMOJI.pattern, "", json.dumps(payload, ensure_ascii=False)))

html = Path(__file__).with_name("report_template.html").read_text()
Path("report.html").write_text(html.replace("/*DATA*/null", json.dumps(payload)))
print(f"Wrote {Path('report.html').resolve()}")
