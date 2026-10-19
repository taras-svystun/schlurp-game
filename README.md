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

## Play

```sh
.venv/bin/schlurp play
```

A window opens for two people sharing the computer. Blue moves first.

- Click one of your pawns. The cells it can reach light up: a solid ring is a clone (a new pawn next to it), a dashed ring is a jump (the pawn moves 2 cells and leaves its cell empty). Click one of them to move there.
- Or click an empty cell next to your pawns to clone there at once.
- Click the picked pawn again to drop it, or click another of your pawns to pick that one. Your pawns that cannot move are dimmed.
- After the move, every enemy pawn next to the cell you landed on turns to your colour.
- The orange ring shows the last move, and a dot the cell a jump left. The panel on the right shows each player's pawns, whose turn it is, what the last move did and the list of moves.

Keys: N starts a new game, Esc quits. Undo, the start menu and playing against an AI come in the next step.

## Run the tests

```sh
.venv/bin/pytest
```

This also checks our rules against the [`ataxx`](https://pypi.org/project/ataxx/) package: the number of move sequences from the start (perft, up to 5 moves deep) and 250 random games played in both engines side by side, compared after every move. It takes about 12 seconds.

Only the quick rule tests, without the reference:

```sh
.venv/bin/pytest tests/test_position.py tests/test_game.py
```

Only the window tests (no real window opens):

```sh
.venv/bin/pytest tests/test_play_window.py
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
