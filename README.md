# Schlurp

Schlurp, the Microscope puzzle from "The 7th Guest" (also known as Ataxx), on your own computer: play against a friend or an AI, and build AI players and compare them.
No internet and no server needed.

The rules we use and the words we use for them are in [CONTEXT.md](CONTEXT.md), and why we chose them in [docs/adr/0002-schlurp-rules.md](docs/adr/0002-schlurp-rules.md). The roadmap is in [docs/PLAN.md](docs/PLAN.md).

## First-time setup

Needs Python 3.11 or newer. Run this once, from the project folder:

```sh
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

Run the second line again after pulling new code, in case new packages were added.

For the web version's tests you also need [Node](https://nodejs.org) 22 or newer. Then run, once and after pulling new code:

```sh
npm ci
```

It installs Pyodide into `node_modules/`, so the tests can run our Python the way the browser does. Without it that one test is skipped.

## Play

```sh
.venv/bin/schlurp play
```

A start menu opens first. For Blue and for Green, pick Person or an AI agent (Random, Greedy or AlphaBeta, see [AI agents](#ai-agents)), pick who moves first, and press Start or Enter.
Two people can share the computer, or you can play against an AI. With an AI agent on both sides, Start opens [Watch](#watch) instead.

- Click one of your pawns. The cells it can reach light up: a solid ring is a clone (a new pawn next to it), a dashed ring is a jump (the pawn moves 2 cells and leaves its cell empty). Click one of them to move there.
- Or click an empty cell next to your pawns to clone there at once.
- Click the picked pawn again to drop it, or click another of your pawns to pick that one. Your pawns that cannot move are dimmed.
- After the move, every enemy pawn next to the cell you landed on turns to your colour.
- The orange ring shows the last move, and a dot the cell a jump left. The panel on the right shows each player's pawns, whose turn it is, what the last move did and the list of moves.
- An AI agent thinks while the window keeps drawing, and plays its move at least 0.7 seconds after yours, so you see your own move land first.

- Press H or the Hint button when you are stuck: Deepening with the `mix` heuristic (see [AI agents](#ai-agents)) thinks for you, for at most half a second, and its move pulses on the board: a yellow ring on the cell to move to, and for a jump a line from the pawn that jumps. It only shows the move; you still play it, or another one. The hint goes away after any move or Undo.

Keys: U or Backspace undoes (one move between two people, or back to your last turn against an AI), N starts a new game with the same players, M goes back to the menu, H shows a hint, Esc quits. The Undo, New, Menu and Hint buttons do the same.

Every finished game is saved, see [Game records](#game-records).

## Watch

Two AI agents play each other in a window, and you see what each one thinks before it moves:

```sh
.venv/bin/schlurp watch Greedy Random
.venv/bin/schlurp watch Greedy Greedy --first green     # Green moves first
.venv/bin/schlurp watch AlphaBeta Greedy                 # AlphaBeta looks 3 moves ahead
.venv/bin/schlurp watch AlphaBeta:2 AlphaBeta            # depth 2 against depth 3
.venv/bin/schlurp watch AlphaBeta:mix AlphaBeta          # the mix heuristic against plain pawns
.venv/bin/schlurp watch Deepening:mix AlphaBeta          # "≤" marks a score that is only an upper bound
.venv/bin/schlurp watch MCTS Greedy                      # scores are MCTS's share of wins in random games, 0.00 to 1.00
```

The first agent plays Blue, the second Green. You can also pick an AI agent for both players in the start menu (`.venv/bin/schlurp play`).

- **Move scores** (on the board): each cell a move can land on shows the best score of those moves, from the point of view of the player to move. The chosen move is yellow; for a jump a line shows which pawn jumps. Greedy's score is the pawn difference after the move; MCTS's is its share of wins in random games, from 0.00 to 1.00; AlphaBeta's is the pawn difference it expects after looking ahead, or ±1000 and more for a won or lost game. Random gives no scores.
- **Expected line**: the moves the agent expects next, starting with its own.
- **Work done**: how many positions it looked at, how many moves ahead, and how long it took.

Each part has a checkbox to hide it. The scores appear once the last move has landed, and the move is played after the time on the speed slider (from 5 seconds down to 0.05).

Keys: Space or P pauses and resumes, S or → plays one move and stays paused, N starts a new game, M goes back to the menu, Esc quits. Every finished Watch game is saved, like Play games.

## Tournament

Many games between two AI agents, with no window, to compare them with numbers:

```sh
.venv/bin/schlurp tournament Random Random
```

It plays 250 random openings of 4 moves, each twice with the agents swapping players (500 games), and prints a report: A's wins, draws and losses, A's points with a 95% confidence interval, the pawn difference at the end, the time per move, and how the games ended. Random against Random takes about a second.

The games run in several processes at once: half the CPU cores by default, so the laptop stays cool. Options:

```sh
.venv/bin/schlurp tournament Random Random --openings 50          # fewer games: 50 openings, 100 games
.venv/bin/schlurp tournament Random Random --opening-moves 6      # longer random openings
.venv/bin/schlurp tournament Random Random --seed 1               # exactly the same games every time
.venv/bin/schlurp tournament Random Random --workers 1            # one process only
.venv/bin/schlurp tournament Random Random --save                 # also save every game in a CSV file
.venv/bin/schlurp tournament --help                               # all options
```

The report ends with the seed it used, so any tournament can be played again with `--seed`.
How to read the confidence interval: [docs/agents/random.md](docs/agents/random.md#what-tournaments-show).

## Game records

Saved games are in the `records` folder of the project (git ignores it):

- `records/games`: one JSON file for each finished Play or Watch game, the newest 100. If you undo and finish the game again, that is saved too.
- `records/tournaments`: one CSV file for each tournament run with `--save`, the newest 10. One row per game, with the whole game in the `record` column.

A JSON file holds the players, who moved first, the moves (`b6 a1c3 ...`), the winner, the score and how the game ended. To look at a saved game in Python:

```python
from pathlib import Path
from schlurp.records import load_game

path = sorted(Path("records/games").iterdir())[-1]   # the newest game
record = load_game(path)
game = record.replay()                                # the whole game, move by move
print(game.positions[10])                             # the board after 10 moves
```

## AI agents

Each agent is explained in its own file in [docs/agents](docs/agents):

- **Random** ([random.md](docs/agents/random.md)): plays any legal move. The baseline every other agent must beat.
- **Greedy** ([greedy.md](docs/agents/greedy.md)): looks one move ahead and plays the move with the best pawn difference. Wins 499 games of 500 against Random.
- **AlphaBeta** ([alphabeta.md](docs/agents/alphabeta.md)): looks 3 moves ahead (my move, the answer, my next move), expects the opponent's best answer, and skips the lines that cannot change its choice. Set the depth after a colon: `AlphaBeta:2` is faster, `AlphaBeta:4` takes seconds per move. Name a heuristic too: `AlphaBeta:mix` is stronger at the same depth but takes about 0.7 s per move.
- **Deepening** ([deepening.md](docs/agents/deepening.md)): AlphaBeta that tries the most promising moves first and looks 1, 2, 3, ... moves ahead until its time is up, then plays the best move of the deepest search it finished. 0.5 s per move unless told otherwise: `Deepening:0.2s` is quicker, `Deepening:2s` deeper, `Deepening:4` searches exactly 4 moves deep whatever the time, and `Deepening:1s:mix` sets the time and the heuristic. `Deepening:mix` is the strongest agent we have, and it gives the hints in Play.
- **MCTS** ([mcts.md](docs/agents/mcts.md)): Monte Carlo tree search. It needs no heuristic: it judges moves by playing many random games to the end, and grows a tree of positions where the playouts look best. 0.5 s per move unless told otherwise: `MCTS:0.2s` sets the time, `MCTS:1000` the number of playouts, `MCTS:1000:2s` both (whichever comes first). Plain MCTS is weak in Ataxx: it beats Random but loses to Greedy, and mcts.md explains why.
- **Heuristics** ([heuristics.md](docs/agents/heuristics.md)): what AlphaBeta guesses where its look-ahead stops. `pawns` (the default), `safe`, `holes`, `exposed`, `mobility`, and `mix` (safe pawns and holes, the best we found). You can try your own weights in the agent name: `AlphaBeta:2:safe=0.5:holes=-1` is `mix` at depth 2.

Compare any two of them:

```sh
.venv/bin/schlurp tournament Greedy Random
.venv/bin/schlurp tournament Greedy Greedy
.venv/bin/schlurp tournament AlphaBeta:2 Greedy
.venv/bin/schlurp tournament AlphaBeta Greedy --openings 100     # about 2 minutes: depth 3 takes 0.15 s per move
.venv/bin/schlurp tournament AlphaBeta:2:mix AlphaBeta:2 --openings 100     # about 4 minutes
.venv/bin/schlurp tournament AlphaBeta:2:safe=1:holes=-0.5 AlphaBeta:2:mix --openings 50     # try your own weights
.venv/bin/schlurp tournament Deepening:0.2s:mix Deepening:0.2s --openings 100     # about 7 minutes
.venv/bin/schlurp tournament Deepening:4 AlphaBeta:3 --openings 20     # a depth, so the games can be repeated exactly
.venv/bin/schlurp tournament MCTS:0.2s Greedy --openings 50     # under a minute: Greedy wins fast
```

## Web version

The web version is being built (see the Web version section of [docs/PLAN.md](docs/PLAN.md)). For now it plays two people on one computer, in a browser:

```sh
.venv/bin/schlurp web
```

Then open http://localhost:8000. Another port: `.venv/bin/schlurp web --port 8080`. Ctrl+C stops it.

- The page loads our own Python into the browser with Pyodide (see [docs/adr/0005](docs/adr/0005-web-engine-in-the-browser-php-passes-moves.md)), so the first visit needs the internet and takes a few seconds. "Loaded in ... s" under the moves shows how long.
- Click a pawn, then a cell: a solid ring is a clone, a dashed ring a jump. Or click an empty cell next to your pawns to clone there. Undo takes back one move. New game starts again, with the player picked in "First".
- `schlurp web` first packs the Python files the page needs into `web/build/schlurp.zip`, so a change in the engine shows after a restart and a reload of the page.

## Run the tests

```sh
.venv/bin/pytest
```

This also checks our rules against the [`ataxx`](https://pypi.org/project/ataxx/) package: the number of move sequences from the start (perft, up to 5 moves deep) and 250 random games played in both engines side by side, compared after every move. All the tests take about 45 seconds.

GitHub runs all the tests again after every push (`.github/workflows/tests.yml`). See the result at https://github.com/taras-svystun/schlurp-game/actions: a red cross means a test failed there.

Only the quick rule tests, without the reference:

```sh
.venv/bin/pytest tests/test_position.py tests/test_game.py
```

Only the window tests (no real window opens):

```sh
.venv/bin/pytest tests/test_play_window.py tests/test_play_against_ai.py tests/test_hint.py tests/test_agent_thread.py tests/test_watch.py
```

Only the agents' tests:

```sh
.venv/bin/pytest tests/test_agents.py tests/test_random_agent.py tests/test_greedy_agent.py tests/test_alphabeta_agent.py tests/test_heuristics.py tests/test_deepening_agent.py tests/test_mcts_agent.py
```

Only the tournament and game record tests:

```sh
.venv/bin/pytest tests/test_tournament.py tests/test_records.py
```

Only the web version's tests (one of them runs Pyodide in Node, see [First-time setup](#first-time-setup)):

```sh
.venv/bin/pytest tests/test_web.py
```

Only the tests against the reference:

```sh
.venv/bin/pytest tests/test_against_ataxx.py
```

## Try the engine in Python

You can play without a window, in a Python shell:

```sh
.venv/bin/python
```

```python
from schlurp.engine import Game, Player

game = Game(first=Player.BLUE)
print(game.position)                          # the board as a picture, B for Blue, G for Green
[str(m) for m in game.position.legal_moves()] # ['f1', 'g1e1', 'g1e2', ...], 16 moves
game.play("b6")                               # Blue clones next to its pawn on a7
game.play("a1c3")                             # Green jumps from a1 to c3
print(game.position)
game.position.pawns(Player.BLUE)              # 3
game.undo()
```

Moves are written like on a chess board: columns a–g from left to right, rows 1–7 from bottom to top. A clone is the cell it lands on (`b6`), a jump is both cells (`a1c3`).

Let an agent choose a move:

```python
from schlurp.agents import make_agent

agent = make_agent("Random", seed=1)
move = agent.choose_move(game.position)
str(move)                                     # like 'b7' or 'g1e3'
game.play(move)
```
