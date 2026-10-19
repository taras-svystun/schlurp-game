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

## Step 2: Play for two people (2026-10-19)

**What:** `schlurp play` opens a Pygame window where two people take turns on one computer. The board sits under a microscope lens, the pawns are blue and green microbes, and every move is animated: the pawn lands (a jumping pawn shrinks away from its cell), then the infected pawns change colour.

**Why:** It is the first way to actually play the game, and the window code is the base for Play against AI and Watch later.

**How:**
- `schlurp/ui/board_view.py` knows where each cell is on the screen (a1 at the bottom left) and draws the lens, the grid, the microbes, the reachable cells and the last move. The lens is drawn once at the start, since it never changes. Microbes are wobbling polygons, drawn smooth with `pygame.gfxdraw`.
- The animation only changes the drawing: the game already has the new position when the animation starts, so a test or an agent never waits for it. It lasts 0.45 s.
- `schlurp/ui/play.py` turns clicks into moves: pick a pawn, see its targets (solid ring for a clone, dashed for a jump), click one. Clicking an empty cell next to your pawns clones at once, since all such clones are the same move. Pawns with no move are dimmed and cannot be picked.
- A side panel shows each player's pawns, whose turn it is, a line about the last move (with "cannot move and passes" when it happens) and the last 10 moves.
- `schlurp/cli.py` is the `schlurp` command. Only `play` exists for now. Pygame is loaded only when a window opens, and a test checks that `schlurp --help` does not load it.
- The tests send fake clicks to the window with no real screen (SDL's "dummy" video driver), and draw every moment of a move, the middle of an animation included.
- Undo, the start menu and Play against an AI come in step 3.

## Step 3: agents, Random, Play against AI, Undo (2026-10-20)

**What:** The `Agent` interface and the Random agent, a start menu, Play against an AI agent, and Undo. `docs/agents/random.md` explains Random.

**Why:** Every AI we build later (Greedy, AlphaBeta, Deepening, MCTS) plugs into the same `Agent` interface, so the window, Watch and Tournament never need to know how an agent thinks. Random is the baseline every later agent must beat.

**How:**
- `schlurp/agents/base.py` has `Agent` and `Thoughts`, as in Awalé from the start: an agent writes `choose_move` (just the move) or `think` (the move with its scores, expected line, positions and depth), and each is built from the other. `think_in_game(game)` is what the window calls. Every agent has its own seeded random generator, so games can be repeated. `make_agent("Random")` builds an agent by its name. This folder never imports Pygame, and a test checks that.
- `RandomAgent` is one line: `self.rng.choice(position.legal_moves())`. Since a pawn has up to 16 jumps but only 8 clones, and clones onto one cell are one move, 77% of Random's moves are jumps. In 2000 games of Random against itself, Blue won 1016 and Green 984, so moving first does not seem to matter much under random play.
- The AI thinks in a background thread (`schlurp/ui/agent_thread.py`), on a copy of the game, so the window keeps drawing. Its move comes at least 0.7 seconds after it starts thinking, which is longer than the 0.45 s animation of your own move. If the agent crashes, the error is raised in the window instead of the game waiting forever.
- Undo goes back to the last position where a person was to move: one move between two people, your move and the AI's against an AI. If the AI is still thinking, its answer is thrown away. Passes need nothing special, since a pass is not a move.
- `schlurp/ui/menu.py` is the start menu: Person or Random for Blue and Green, and who moves first. It does not start a game with no person, because AI against AI is Watch (step 5). `schlurp play` now opens the menu first.
- The window tests use small fake agents (one always plays its first legal move, one waits until the test lets it answer, one crashes), so they do not depend on Random.
- New idea in `docs/PLAN.md` under "Later": an online web version, hosted on the website of Pascal Peyremorte, Taras's friend who wrote the Delphi Schlurp, with Play against agents, Watch, tournaments and game records.
