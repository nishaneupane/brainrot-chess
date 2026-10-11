"""Breeding: a winner and a loser go in, a child comes out.

LLM mode: the model is the league's unhinged coach. It reads both bots' genes and
records and writes the child: new genes, a playbook, a name, a personality and
trash talk. Mock mode (no API key): crossover + random mutation, for offline dev.

Env vars (any OpenAI-compatible endpoint, e.g. Luminal's):
  LLM_BASE_URL  (ends in /v1)   LLM_API_KEY   LLM_MODEL
"""
import json
import os
import re
import urllib.request

from agents import GENES, NAMES, PERSONALITIES, Agent


def llm_enabled():
    return bool(os.getenv("LLM_API_KEY") and os.getenv("LLM_BASE_URL"))


def chat(messages, temperature=1.0):
    url = os.environ["LLM_BASE_URL"].rstrip("/") + "/chat/completions"
    body = json.dumps({"model": os.getenv("LLM_MODEL", "deepseek-ai/DeepSeek-V3.1"),
                       "messages": messages, "temperature": temperature,
                       "response_format": {"type": "json_object"}}).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {os.environ['LLM_API_KEY']}"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"]


def describe(a):
    return json.dumps({"name": a.name, "personality": a.personality,
                       "record": {"wins": a.wins, "losses": a.losses, "draws": a.draws},
                       "genes": a.genes, "playbook": a.playbook}, indent=1)


PROMPT = """You are the chronically online head coach of the Brainrot Chess League,
where chess bots evolve. You talk in Gen Z / Gen Alpha brainrot (aura, mog, fanum tax,
rizz, Ohio, sigma, cooked, no cap, fr fr, glazing, delulu, L + ratio) but your
chess reasoning is actually smart. Keep it clean enough to show on a projector:
no sexual slang, no slurs, no emojis, roast the bots not real people.

Each bot scores every legal move with these weighted genes (about -1..1, chaos 0..1):
{genes}

THE W (keep what works):
{winner}

THE L (getting deleted, learn from its mistakes):
{loser}

Breed a CHILD that would mog both. Think about which genes made the W win.
Reply ONLY with JSON:
{{"genes": {{<every gene name>: number}},
  "playbook": "<2 sentences, the child's actual strategy, in brainrot voice>",
  "name": "<brainrot chess name, max 3 words, not any of: {taken}>",
  "personality": "<short brainrot personality>",
  "trash_talk": "<one line of PG-13 brainrot trash talk aimed at the L>"}}"""


def clamp(genes, fallback):
    out = {}
    for g in GENES:
        try:
            v = float(genes.get(g, fallback[g]))
        except (TypeError, ValueError):
            v = fallback[g]
        out[g] = round(max(0.0 if g == "chaos" else -1.5, min(1.5, v)), 3)
    return out


def breed_llm(winner, loser, generation, taken):
    raw = chat([{"role": "user", "content": PROMPT.format(
        genes="\n".join(f"- {k}: {v}" for k, v in GENES.items()),
        winner=describe(winner), loser=describe(loser), taken=", ".join(sorted(taken)[-40:]))}])
    d = json.loads(re.sub(r"^```(?:json)?|```$", "", raw.strip()).strip())
    return Agent(clamp(d.get("genes", {}), winner.genes), str(d.get("name", "Unnamed Menace"))[:40],
                 d.get("personality", winner.personality), generation, [winner.id, loser.id],
                 d.get("playbook", ""), d.get("trash_talk", ""))


MOCK_TALK = [
    "{l} got deleted and the bloodline's aura went up 10000 fr",
    "{l} really thought it was him. it was not him",
    "rest in pieces {l}. literally. you hung all of them",
    "got {w}'s rizz and none of {l}'s skill issue. built different",
    "{l} played like it was their first day in Ohio",
    "{l} said 'trust the process'. the process was getting fanum taxed",
    "{l} is so cooked they're serving it at the dining hall",
    "not me inheriting the W genes while {l} touches grass permanently",
]


def breed_mock(winner, loser, generation, taken, rng):
    genes = {g: (winner.genes[g] if rng.random() < 0.75 else loser.genes[g]) + rng.gauss(0, 0.25)
             for g in GENES}
    genes = clamp(genes, winner.genes)
    name = rng.choice([n for n in NAMES if n not in taken] or NAMES)
    if name in taken:
        name = f"{name.split(' Jr.')[0]} Jr. {generation}"
    best = max((g for g in GENES if g != "chaos"), key=lambda g: genes[g])
    return Agent(genes, name, rng.choice(PERSONALITIES), generation, [winner.id, loser.id],
                 f"inherited {winner.name}'s aura and maxed out {best.replace('_', ' ')}. no cap.",
                 rng.choice(MOCK_TALK).format(l=loser.name, w=winner.name))


def breed(winner, loser, generation, taken, rng):
    if llm_enabled():
        try:
            return breed_llm(winner, loser, generation, taken)
        except Exception as e:  # one bad reply never kills the run
            print(f"  ! LLM breed failed ({e.__class__.__name__}: {e}); using mutation")
    return breed_mock(winner, loser, generation, taken, rng)
