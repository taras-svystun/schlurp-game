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

## Step 5: Greedy and the Hint button (2026-10-20)

**What:** The Greedy agent, a Hint button in Play, and tournaments against Random and itself. `docs/agents/greedy.md` explains Greedy.

**Why:** Greedy is the first agent that looks ahead, even if only one move, and the first one with thoughts to show. It is the agent we need for hints, and for building the thoughts panel of Watch next.

**How:**
- `GreedyAgent.think` tries every legal move and scores it by the pawn difference after it, choosing at random between equal moves. A clone gains `1 + 2k` and a jump `2k` for `k` infected pawns, so it jumps only when a jump infects more.
- Hint: H or the Hint button asks a Greedy agent of its own (never one of the players) in a background thread, and the board shows its move with a pulsing ring, and a line for a jump. The hint is cancelled or dropped on any move, Undo, New or Menu.
- The four buttons got short labels (Undo, New, Menu, Hint) to fit the panel; the keys are on two lines above them. A test checks that the buttons and the keys fit, and it caught the first version of the keys line running off the window.
- The start menu now offers every agent in `AGENTS`, so a new agent shows up there by itself.
- Greedy against Random: 499 of 500 games (99.8% ± 0.4%), 11 moves per game, nearly all ending with Random losing every pawn. Greedy against Greedy: 49.2% ± 4.4%, even; Blue won 272 of 500, so moving first may help a little when both players play well.

## Step 6: Watch (2026-10-20)

**What:** `schlurp watch A B`, or two AI agents in the start menu, opens a window where the agents play each other with their thoughts shown: move scores on the board, the expected line and the work done, each with a checkbox. Pause, Step and a speed slider control the game.

**Why:** A tournament says which agent wins; Watch shows why. Seeing Greedy's scores on the board makes its choices, and its blind spots, easy to follow, and it will matter more for AlphaBeta and MCTS.

**How:**
- Play and Watch now share `schlurp/ui/game_screen.py`: the game, the AI thread, the message about each move, saving the record and the top of the side panel. `PlayScreen` keeps clicks, Undo and Hint; `WatchScreen` adds Pause, Step, the slider and the thoughts. This follows Awalé.
- One clone and several jumps can land on the same cell, and a cell has room for one number, so each cell shows the best score of the moves landing there. The chosen move is yellow, with a line from the pawn for a jump, drawn like the hint in Play.
- A move is played once the agent is done and the previous move has landed, plus the time on the slider. So the thoughts stay on the board for the same time whether an agent thinks for a microsecond or a second. At high speed the animation gets shorter too.
- The slider works like a volume knob: each step along it multiplies the speed by the same amount, from 5 seconds to 0.05.
- Watch refuses one agent object for both players: each needs its own random generator, and since `docs/adr/0004` one object would also make the two players wait for each other.
- The control tests check that every button label fits its button; they caught "Resume (Space)", so the button now says "Resume (P)" (Space still works).

## Step 7: AlphaBeta with the pawns heuristic (2026-10-20)

**What:** The AlphaBeta agent, which looks 3 moves ahead, and the `pawns` heuristic. It now gives the hints in Play. `docs/agents/alphabeta.md` explains it.

**Why:** Greedy never looks at the opponent's answer, so it leaves holes and loses whole groups. Searching a few moves deep, expecting the opponent's best answer, is the first real step towards a strong agent.

**How:**
- `schlurp/agents/heuristics.py` holds `pawns` (my pawns minus the opponent's) and a `HEURISTICS` table, ready for step 8.
- `AlphaBetaAgent` is Minimax with alpha-beta pruning. We wrote no plain Minimax agent (see CLAUDE.md); plain Minimax lives only in the tests, where AlphaBeta must give exactly its scores at depths 1, 2 and 3 on real positions.
- A finished game is worth 100 plus the depth left, so a win beats any pawn count and a quick win beats a slow one. After a pass the same player moves again, so the search asks whose turn it is at every position.
- Every root move is searched with the full window, so each gets its exact score for Watch and ties are broken at random. Pruning still saved 4.7 times the positions at depth 3.
- The search checks `should_stop()` (see `docs/adr/0004`), so Undo, New and Menu stop it at once. This is the first agent that needs it.
- `make_agent` takes options after colons: `AlphaBeta:2`, `AlphaBeta:3:pawns`.
- Depth 3 by default: 0.15 s per move on average, 0.4 s at worst. Depth 4 takes 3 s on average and waits for move ordering in step 9.
- Tournaments (depth 3 kept to 200 games, so each one stayed under 10 minutes): AlphaBeta:2 beats Greedy 92.4% ± 2.3%, AlphaBeta:3 beats Greedy 94.0% ± 3.3%, and AlphaBeta:3 beats AlphaBeta:2 89.5% ± 4.3%. Against a weak agent two strong ones look alike; head to head the extra depth shows.

## Step 8: better heuristics (2026-10-20)

**What:** Four features for AlphaBeta's heuristic (mobility, safe pawns, exposed cells, holes), weights chosen by tournaments, and the `mix` heuristic: pawns, plus half a pawn per safe pawn, minus a pawn per hole. `docs/agents/heuristics.md` explains them.

**Why:** `pawns` sees how many pawns each player has but not how they stand. A packed group and a group full of holes count the same, though the opponent can jump into the holes next move.

**How:**
- Each feature is "mine minus the opponent's", and `weighted` adds features times weights to `pawns`, as in Awalé. Agent names can carry weights (`AlphaBeta:2:safe=0.5:holes=-1`), so tournaments, whose worker processes build agents from names, can try any mix, and so can Taras.
- Mobility can pass 100 moves, so a guess could have looked better than a won game (100). `WIN` is now 1000 and lives in `heuristics.py`; `weighted` refuses weights that could reach it, and a test checks every named heuristic.
- Three stages of tournaments at depth 2, each tournament under 10 minutes: each feature alone against `pawns`, then mixes against the best single feature (`safe=0.5`), then the winner again with a new seed, because trying many weights finds some winners by luck. Safe pawns helped most (79%), holes helped only with a negative weight (70%, and 21.5% with a positive one), exposed cells a little, mobility not at all while being the slowest.
- `mix` beats `pawns` 71.8% ± 6.1% at depth 2 and 73.3% ± 11.3% at depth 3, but loses 78% of games to `pawns` one move deeper: depth is worth more than a better guess. AlphaBeta keeps `pawns` by default, which stays fast for hints; `AlphaBeta:mix` is there to choose.
- In all, the step's tournaments ran for about 45 minutes, in short runs. Stage 2 took 17 minutes instead of the 10 estimated, because the mixes think slower than measured alone.
