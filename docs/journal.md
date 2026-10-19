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

## Step 4: Tournament and game records (2026-10-20)

**What:** `schlurp tournament A B` plays many games between two AI agents with no window and prints a report. Every finished Play game is saved as a JSON game record, and a tournament as a CSV with `--save`.

**Why:** From now on every agent must prove it is stronger with numbers, not by eye. Game records let us look at any game again, and Watch and the web version will read them too.

**How:**
- `schlurp/tournament.py` follows the Awalé tournament. 250 random openings of 4 moves, each played twice with the agents swapping players, so neither gets the luckier openings or the better player more often. All the random choices (openings, each agent's seed) are made before any game starts, so one seed gives the same games with 1 process or 8.
- The games run in half the CPU cores by default, not all of them, so the laptop stays cool; `--workers` changes it. Each worker process builds its agents from their names, because macOS starts workers fresh and they cannot share objects with the main process.
- With no `--seed`, the tournament picks one and prints it at the end of the report, so any tournament, even an odd-looking one, can be played again.
- An agent that plays an illegal move stops the tournament with its name, the game number and the position, instead of a bare error from the engine.
- The report gives A's points with a 95% confidence interval, the pawn difference, the time per move, wins by player, and how the games ended. For that `Result` got `ended_by` ("full board", "no pawns" or "fifty-move rule"), read from the score alone; the window uses it too, instead of its own guess.
- Random against Random, 500 games in 0.9 seconds: 51.8% ± 4.4%, so even, as it should be. A 40-game run showed the other side of the interval: it called Random stronger than itself, which a 95% interval does about 1 time in 20. `docs/agents/random.md` explains how to read it.
- `schlurp/records.py` holds `GameRecord`: the players, who moved first, the moves in standard notation, and the result. Moves like `b6` do not say who made them, so replaying them from the start tells whose turn each one was, passes included. `replay()` also checks that the moves really give the saved result. We keep the newest 100 games and 10 tournaments.
- Tests: a shared fixture in `tests/conftest.py` makes every test save its records in an empty temporary folder, never in the real `records/`.

## One agent in one thread at a time (2026-10-20)

**What:** In the window an agent never thinks in two threads at once, and Undo, New and Menu cancel a move that is no longer wanted. Greedy now comes before Watch in the plan.

**Why:** Undo used to forget the thinking thread, and the next AI turn started a second thread with the same agent object. Harmless with Random, but search agents keep data on the agent while they think, and two threads would mix it up. The forgotten search also kept a CPU core busy.

**How:**
- `docs/adr/0004` explains the choice and why it cannot freeze the window or deadlock.
- `AgentThread` takes a lock for its agent inside the background thread, so a new thread waits there, never in the window, until the old one is done.
- `AgentThread.cancel()` sets an event that only that thread has. The agent reads it through `Agent.should_stop()`; a long search will check it and return at once. A thread cancelled before it got the lock never calls the agent.
- New tests in `tests/test_agent_thread.py` use an agent that thinks until told to stop and counts how many threads are inside it. On the old code the main test fails with two threads inside the agent; now it is always one. The thread tests passed 20 runs out of 20.
- We moved Greedy before Watch: Watch is mostly the thoughts panel, and Random has no thoughts to show.
