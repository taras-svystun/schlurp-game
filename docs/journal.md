# Journal

A short, plain-English history of each finished step: what we did, why, and how. Newest at the bottom.

## Step 0: research and planning (2026-10-19)

**What:** We agreed on the rules and on the words we use, and wrote the glossary (`CONTEXT.md`), the plan (`docs/PLAN.md`), `CLAUDE.md` and three decision records (`docs/adr/0001`–`0003`). No game code yet.

**Why:** We wanted to agree on the rules and on how to check them before writing any code, so the code, the docs and our conversations all mean the same thing. The project follows the way the Awalé project was built.

**How:**
- We read the Delphi source of Pascal Peyremorte's Schlurp (version 2.21): a 7 × 7 board with no blocked cells, the start corners, automatic passes, and no rule that stops a game of endless jumps. We added the fifty-move rule from standard Ataxx for that.
- OpenSpiel has no Ataxx, so the `ataxx` package on PyPI becomes our reference for the rules. Its perft from the start is 16, 256, 6460, 155888, 4752668 at depths 1–5.
- We counted clones onto the same cell as one move, so agents never search the same position twice.
- We measured a tuple board against a bitboard in Python: the bitboard was only 1.4 times faster at perft and slower at random games, so we start with the easier tuple.
- In 2000 random games the median game was 195 moves, the longest run of jumps was 53, and no game ended in a tie.

## Step 1: the game engine (2026-10-19)

**What:** `schlurp/engine.py` holds all the rules. `Position` is one moment of the game and knows how to play one move. `Game` keeps the whole game and can undo. There is no window yet.

**Why:** Everything else (the window, the AI agents, tournaments) is built on these rules, so they must be right first. The engine has no Pygame in it, so a web version can use it later too; a test checks that.

**How:**
- The board is a tuple of 49 numbers (0 empty, 1 Blue, 2 Green), with a1 at index 0. The neighbours and jump targets of every cell are worked out once, so the rules never check the edges of the board.
- A `Move` has a target and, for a jump only, a source. Clones onto one cell are one move. `str(move)` gives `c3` or `a1c3`, and `Game.play` also takes those strings.
- A pass happens inside `Position.play`: if the opponent cannot move, the turn stays with the mover. So the player to move always has a move until the game ends, and `Game.moves` needs no pass entries. `Position.setup` passes too, for positions drawn by hand.
- The engine does not check "neither player can move" on its own: with no blocked cells it only happens on a full board or with no pawns left. `ends_game` explains why.
- Tests first on small positions drawn as pictures: clone, jump, infections in the middle and in a corner, illegal moves, pass, wipe-out, full board, the fifty-move rule.
- Then against the `ataxx` package: perft 16, 256, 6460, 155888 and 4752668 from the start, 150 random games compared after every move (with 18 passes and 6 wipe-outs), and 100 games of players who mostly jump without infecting, so that 99 of them end by the fifty-move rule. They all matched the first time.
- Pawn counts after every move are checked too: a clone adds 1 plus the infected pawns, a jump only the infected ones, and nothing changes outside the landing cell, its neighbours and the cell a jump left.
- Speed: perft(5) takes 2.4 s inside pytest, about twice the throwaway version from step 0. The profiler shows building the list of moves is most of the time; making `Move` named tuples and checking for a pass after each move add a little. We look at speed again in the Deepening step.
