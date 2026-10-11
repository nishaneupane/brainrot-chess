"""Breeding: a winner and a loser go in, a child comes out.

LLM mode: the model acts as a coach. It reads both bots' genes and records and
writes the child's genes, a short strategy note and a name. Mock mode (no API
key): crossover + random mutation, for offline development.

Env vars (any OpenAI-compatible endpoint, e.g. Luminal's):
  LLM_BASE_URL  (ends in /v1)   LLM_API_KEY   LLM_MODEL
"""
import json
import os
import re
import urllib.request

from agents import GENES, NAMES, Agent, play_style


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
    return json.dumps({"name": a.name,
                       "record": {"wins": a.wins, "losses": a.losses, "draws": a.draws},
                       "genes": a.genes, "playbook": a.playbook}, indent=1)


PROMPT = """You are the coach of a league of evolving chess bots.
Each bot scores every legal move with these weighted genes (about -1..1, randomness 0..1):
{genes}

WINNER (keep what works):
{winner}

LOSER (being replaced; learn from its mistakes):
{loser}

Create a CHILD bot that should beat both. Reason about which genes caused the win.
Write in plain, clear English. Only the name should be playful: give it a funny
Gen Z / brainrot-style chess name (like "Skibidi Sicilian" or "Rizzler Rook"),
max 3 words, clean enough for a projector, no emojis, not any of: {taken}.
Reply ONLY with JSON:
{{"genes": {{<every gene name>: number}},
  "playbook": "<1-2 plain sentences: the child's strategy and why it should win>",
  "name": "<name>"}}"""


def clamp(genes, fallback):
    out = {}
    for g in GENES:
        try:
            v = float(genes.get(g, fallback[g]))
        except (TypeError, ValueError):
            v = fallback[g]
        out[g] = round(max(0.0 if g == "randomness" else -1.5, min(1.5, v)), 3)
    return out


def breed_llm(winner, loser, generation, taken):
    raw = chat([{"role": "user", "content": PROMPT.format(
        genes="\n".join(f"- {k}: {v}" for k, v in GENES.items()),
        winner=describe(winner), loser=describe(loser), taken=", ".join(sorted(taken)[-40:]))}])
    d = json.loads(re.sub(r"^```(?:json)?|```$", "", raw.strip()).strip())
    genes = clamp(d.get("genes", {}), winner.genes)
    return Agent(genes, str(d.get("name", "Unnamed Bot"))[:40], play_style(genes), generation,
                 [winner.id, loser.id], d.get("playbook", ""))


def breed_mock(winner, loser, generation, taken, rng):
    genes = {g: (winner.genes[g] if rng.random() < 0.75 else loser.genes[g]) + rng.gauss(0, 0.25)
             for g in GENES}
    genes = clamp(genes, winner.genes)
    name = rng.choice([n for n in NAMES if n not in taken] or NAMES)
    if name in taken:
        name = f"{name.split(' Jr.')[0]} Jr. {generation}"
    return Agent(genes, name, play_style(genes), generation, [winner.id, loser.id],
                 f"Child of {winner.name} (winner) and {loser.name}, with small random mutations.")


def breed(winner, loser, generation, taken, rng):
    if llm_enabled():
        try:
            return breed_llm(winner, loser, generation, taken)
        except Exception as e:  # one bad reply never kills the run
            print(f"  ! LLM breed failed ({e.__class__.__name__}: {e}); using mutation")
    return breed_mock(winner, loser, generation, taken, rng)
