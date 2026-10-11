# Brainrot Chess League

Chess bots that evolve. Every generation they play a round robin, everyone gets
tested against the **NPC Bot** (takes free mates and juicy captures, otherwise
random), and the bottom half is eliminated and replaced by children of the top half.
The LLM is the coach that breeds them (and names them; the names are the only brainrot part).

## Run it

```bash
pip install -r requirements.txt
python evolve.py            # offline mock mode, no API key needed (~5 min)
python serve.py             # http://127.0.0.1:8000 - the report, plus an arena to play the bots
```

Faster test run: `python evolve.py --gens 4 --npc-games 10`

`serve.py` re-reads the run file on every request, so you can leave it running,
re-run `evolve.py`, and just refresh. Options: `--port`, `--host`, `--run <file>`,
`--no-browser`.

Want a single file to hand someone instead of a server?

```bash
python report.py            # writes report.html (chart, replays, leaderboard, lineage)
```

The saved file carries the whole report; the arena tab just explains that it needs
the server, since there is no bot on the other end of a static page.

### Play a bot

The **Play a bot** tab lets you take on any bot the league ever bred, including
eliminated ones and the NPC baseline. Pick an opponent, pick a colour, click a
piece and then a highlighted square. The server is the referee: `python-chess`
decides what is legal, the bot answers with the same gene-scored move it uses in
the league, and the commentary feed is the same one the replays use.

| Endpoint | What |
|---|---|
| `GET /` | The report, rendered live from the run file |
| `GET /api/roster` | Every playable bot with its generation, style and playbook |
| `POST /api/new` | `{opponent, color}` -> a new game and its first position |
| `POST /api/move` | `{game, uci}` -> your move, the bot's reply, and the new state |

Games live in the server's memory, so they end when you stop it.

### Encoding

The page is built to survive being passed around: `report.py` and `storage.py`
read and write explicit UTF-8 rather than the machine's locale encoding, the
chess glyphs and punctuation in the template are `\uXXXX` escapes, and the data
is serialised with `ensure_ascii`. The result is a pure-ASCII document that
decodes identically as ASCII, UTF-8, latin-1 or cp1252, so the board renders the
same whether it is opened from disk on Windows, served by a host that guesses
the charset wrong, or emailed to someone.

## Real LLM breeding (Luminal / any OpenAI-compatible endpoint)

```bash
export LLM_BASE_URL="<endpoint from the hackathon docs, ending in /v1>"
export LLM_API_KEY="..."
export LLM_MODEL="<DeepSeek or GLM model id>"
python evolve.py
```

The LLM only runs when breeding: 4 calls per generation, ~48 for a full run. It
reads the winner's and loser's genes and records, then writes the child's genes,
a short plain-English strategy, and a brainrot-style name. If a call fails, that child falls back
to random mutation so the run never dies.

## MongoDB (for the prize)

```bash
pip install pymongo
export MONGODB_URI="mongodb+srv://..."
```

Writes `agents`, `matches` and `generations` collections. Every agent stores its
`parents`, which is what the bloodline is built from.

## How a bot thinks

Each bot has 10 genes (greed, paranoia, mate_hunter, checks, center_control,
activity, development, king_safety, pawn_pushing, randomness). It scores every legal
move with them, one move deep plus a "can my piece be captured next move"
check. Fast enough for thousands of games, dumb enough that evolution matters.

Games over 80 moves each go to a judges' decision: whoever is up 3+ points of
material wins, otherwise draw.

## Who owns what

| File | What | Who |
|---|---|---|
| `game.py` | NPC bot, game loop, move commentary | you |
| `agents.py` | Genes, move scoring, bot names | you (logic), her (`NAMES`) |
| `breeder.py` | LLM coach prompt + mock mutation | you (logic), her (naming style in `PROMPT`) |
| `evolve.py` | The loop | you |
| `storage.py` | JSON + MongoDB logging | you |
| `serve.py` | Localhost server + play-a-bot API | you |
| `report.py` | Run file -> page | you |
| `report_template.html` | The demo page and the arena | her |
