"""Run the Brainrot Chess League.

  python evolve.py                       # offline mock mode, ~2 min
  python evolve.py --gens 8 --pop 8
  LLM_BASE_URL=... LLM_API_KEY=... LLM_MODEL=... python evolve.py

Each generation: round robin -> everyone plays the NPC bot (the "it got smarter"
number) -> the bottom half is eliminated and replaced by children of the top half.
Then `python report.py` builds the page.
"""
import argparse
import os
import random
import time
from itertools import combinations

from agents import random_agent
from breeder import breed, llm_enabled
from game import NPCBot, play
from storage import Store


def points(a):
    return 100 * a.wins - 50 * a.losses + 10 * a.draws


def tournament(pop, gen, store, rng):
    for a in pop:
        a.reset_record()
    for a, b in combinations(pop, 2):
        for white, black in ((a, b), (b, a)):
            w, info = play(white, black, rng)
            if w is None:
                white.draws += 1; black.draws += 1
                winner = None
            else:
                win, lose = (white, black) if w == 0 else (black, white)
                win.wins += 1; lose.losses += 1
                winner = win.id
            store.match(gen, white.id, black.id, winner, info["moves"], "tournament")


def vs_npc(agent, gen, store, rng, games):
    npc, wins = NPCBot(), 0
    for g in range(games):
        white = g % 2 == 0
        w, info = play(agent, npc, rng) if white else play(npc, agent, rng)
        won = w == (0 if white else 1)
        wins += won
        if g < 2:
            store.match(gen, *((agent.id, "npc") if white else ("npc", agent.id)),
                        agent.id if won else (None if w is None else "npc"), info["moves"], "npc")
    return wins / games


def featured_game(agent, rng, decisive=True):
    """A fully recorded game (positions + commentary) vs the NPC for the replay."""
    for _ in range(6 if decisive else 1):  # retry for a decisive game for the demo
        w, info = play(agent, NPCBot(), rng, record=True)
        if w is not None:
            break
    return info | {"white": agent.id, "black": "npc",
                   "winner": agent.id if w == 0 else ("npc" if w == 1 else None)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gens", type=int, default=12)
    ap.add_argument("--pop", type=int, default=8)
    ap.add_argument("--npc-games", type=int, default=20)
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    store = Store(time.strftime("run-%Y%m%d-%H%M%S"))
    print("Brainrot Chess League")
    print(f"Breeding: {'LLM (' + os.getenv('LLM_MODEL', '?') + ')' if llm_enabled() else 'mock mutation (no LLM key set)'}\n")

    names = set()
    pop = [random_agent(rng, names) for _ in range(args.pop)]
    for a in pop:
        store.agent(a)

    for gen in range(args.gens + 1):
        tournament(pop, gen, store, rng)
        rates = {a.id: vs_npc(a, gen, store, rng, args.npc_games) for a in pop}
        pop.sort(key=lambda a: (a.score, rates[a.id]), reverse=True)
        champ = pop[0]
        store.generation({
            "generation": gen,
            "best_vs_npc": max(rates.values()),
            "avg_vs_npc": sum(rates.values()) / len(rates),
            "champion": champ.id,
            "standings": [{"id": a.id, "name": a.name, "wins": a.wins, "losses": a.losses,
                           "draws": a.draws, "points": points(a), "vs_npc": rates[a.id]} for a in pop],
        })
        print(f"Gen {gen:>2} | avg win rate vs NPC {sum(rates.values()) / len(rates):.0%} | "
              f"best {max(rates.values()):.0%} | champ: {champ.name} ({points(champ):+} pts)")
        if gen == 0:  # the weakest gen-0 bot, for the "before" replay
            clown = min(pop, key=lambda a: rates[a.id])
            store.data["replay_before"] = featured_game(clown, rng, decisive=False)

        if gen == args.gens:
            store.data["replay_after"] = featured_game(champ, rng)
            break
        half = len(pop) // 2
        winners, losers = pop[:half], pop[half:]
        children = []
        for i, loser in enumerate(losers):
            parent = winners[i % len(winners)]
            child = breed(parent, loser, gen + 1, names, rng)
            base, k = child.name, 2
            while child.name in names:
                child.name = f"{base} {['', '', 'II', 'III', 'IV', 'V'][k] if k < 6 else k}"
                k += 1
            names.add(child.name)
            store.agent(child)
            children.append(child)
            print(f"   {loser.name} eliminated -> new bot {child.name}")
        pop = winners + children

    path = store.save()
    print(f"\nSaved {path}. Now run: python report.py")


if __name__ == "__main__":
    main()
