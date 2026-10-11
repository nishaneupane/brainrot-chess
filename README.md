# Brainrot Chess League

Chess bots that evolve. Every generation they play a round robin, everyone gets
tested against the **NPC Bot** (takes free mates and juicy captures, otherwise
random), and the bottom half gets deleted and replaced by children of the top half.
The LLM is the coach that breeds them, and it talks entirely in brainrot.

## Run it

```bash
pip install -r requirements.txt
python evolve.py            # offline mock mode, no API key needed (~5 min)
python report.py            # builds report.html: chart, replays w/ commentary, aura leaderboard, bloodline
```

Faster test run: `python evolve.py --gens 4 --npc-games 10`

## Real LLM breeding (Luminal / any OpenAI-compatible endpoint)

```bash
export LLM_BASE_URL="<endpoint from the hackathon docs, ending in /v1>"
export LLM_API_KEY="..."
export LLM_MODEL="<DeepSeek or GLM model id>"
python evolve.py
```

The LLM only runs when breeding: 4 calls per generation, ~48 for a full run. It
reads the W's and the L's genes and records, then writes the child's genes,
playbook, name, personality and trash talk. If a call fails, that child falls back
to random mutation so the run never dies.

## MongoDB (for the prize)

```bash
pip install pymongo
export MONGODB_URI="mongodb+srv://..."
```

Writes `agents`, `matches` and `generations` collections. Every agent stores its
`parents`, which is what the bloodline is built from.

## How a bot thinks

Each bot has 10 genes (greed, paranoia, mate_hunter, check_spam, center_rizz,
activity, development, king_safety, pawn_pushing, chaos). It scores every legal
move with them, one move deep plus a "can my piece get fanum taxed next move"
check. Fast enough for thousands of games, dumb enough that evolution matters.

Games over 80 moves each go to a judges' decision: whoever is up 3+ points of
material wins, otherwise draw.

## Who owns what

| File | What | Who |
|---|---|---|
| `game.py` | NPC bot, game loop, move commentary lines | you (logic), her (`commentary` lines) |
| `agents.py` | Genes, move scoring, starting names + personalities | you (logic), her (`NAMES`, `PERSONALITIES`) |
| `breeder.py` | LLM coach prompt + mock trash talk | you (logic), her (`PROMPT` voice, `MOCK_TALK`) |
| `evolve.py` | The loop | you |
| `storage.py` | JSON + MongoDB logging | you |
| `report_template.html` | The demo page | her |
