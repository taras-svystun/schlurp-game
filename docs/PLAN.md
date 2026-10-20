# Plan

Words in **bold** are defined in `../CONTEXT.md`.

## What we agreed

**Rules.** Schlurp as in Pascal Peyremorte's version, the 7th Guest Microscope puzzle (see `adr/0002`):
- a 7 × 7 **board** with no blocked cells; Blue on the top-left and bottom-right corners, Green on the other two; Blue moves first unless the menu says otherwise;
- a move is a **clone** or a **jump**, then every enemy pawn next to the landing cell is **infected**;
- clones onto the same cell from different pawns are one move;
- a player who cannot move **passes** automatically;
- the game ends when the board is full, a player has no pawns, or neither can move; more pawns wins, equal is a draw;
- the **fifty-move rule** from standard Ataxx: 100 jumps in a row end the game in a draw;
- moves in standard Ataxx notation: `c3` for a clone, `a1c3` for a jump.

**Tech.**
- Python 3.11 with a plain `venv` and `pip`, `pytest` for tests, Pygame for the window. The package is `schlurp`, the command is `schlurp play`, `schlurp watch A B`, `schlurp tournament A B`.
- Our own engine in plain Python, checked against the `ataxx` package (pinned to 2.2.0, tests only): perft from the start, thousands of random games compared move by move, hand-checked positions, and properties that always hold (see `adr/0001`).
- The board is a tuple of 49 cells inside an immutable `Position`; agents only use its methods, so a bitboard can replace it later (see `adr/0003`).
- The engine and the agents never import Pygame, so a web version can be added later as just another front end. A test checks this.

**Play** (window):
- two people on one computer, or a person against an AI;
- click one of your pawns, and the cells it can reach light up, clones and jumps drawn differently; click a cell to move there. Clicking the pawn again drops it, clicking another of your pawns picks that one. Clicking an empty cell next to your pawns clones there at once;
- a side panel with each player's pawns, whose turn it is, and the list of moves;
- a light microscope look: a dark lab background, the board inside a round lens, blue and green microbes, short animations for clone, jump and infect, all drawn by Pygame (no outside images or sounds);
- Undo: one move between two people, and back to your last turn against an AI;
- a start menu to pick the agents for Blue and Green and who moves first;
- a Hint button.

**Watch** (window):
- an AI plays an AI;
- pause, step, and a speed slider;
- a **thoughts** panel with a checkbox for each part: move scores on the board, expected line of play, and work done (positions, depth, time).

**Tournament** (terminal):
- **random openings** of 4 moves, each played twice with the agents swapping players; 250 openings (500 games) by default;
- reports win / draw / loss with a 95% confidence interval, the average pawn difference and the time per move;
- writes a CSV and uses half the CPU cores, so the laptop stays cool; `--workers` changes that;
- with no `--seed`, picks one and prints it, so any tournament can be played again.

**Game records.**
- JSON files in `records/games`; we keep the last 100 Play and Watch games.
- A tournament is saved as CSV only with `--save`, and we keep the last 10.

**AI thinking.**
- Every agent has `think()`, which returns **thoughts**, and `think_in_game(game)`.
- Agents run in a background thread so the window stays responsive. An agent never thinks in two threads at once, and a search checks `should_stop()` so Undo can cancel it (see `adr/0004`).
- No plain Minimax agent: search starts at alpha-beta, to keep tournaments short and the laptop cool.
- Greedy plays the move that gives the best pawn difference right after it, choosing at random between equal moves.
- Heuristics to try for AlphaBeta, each "mine minus the opponent's": pawns, mobility, safe pawns (no empty neighbour), exposed cells (empty cells next to my pawns), holes left by jumps. Tournaments choose the weights.

## Steps

- [x] 1. Engine and tests against the `ataxx` package.
- [x] 2. Play for two people in Pygame, with the microscope look, and a README with run commands.
- [x] 3. Agent interface, the Random agent, Play against AI, Undo.
- [x] 4. Tournament and game records. Random vs Random should give about 50/50.
- [x] 5. Greedy agent and the Hint button, then a tournament.
- [x] 6. Watch with the thoughts panel.
- [x] 7. AlphaBeta with the `pawns` heuristic, then a tournament.
- [x] 8. Better heuristics: mobility, safe pawns, exposed cells, holes; then tournaments to choose the weights.
- [x] 9. Deepening: move ordering, iterative deepening and a time limit.
- [x] 10. MCTS.
- [x] 11. Tidy-up: CI on GitHub, packages found by `pyproject.toml`, agent errors shown in the window.

After each agent step, run a tournament against the agents we already have, to see if the new one is really stronger.

## Web version

Pascal Peyremorte, who wrote the Delphi Schlurp, is Taras's friend and offers to host it on his website. The web version is not a copy of the Python one. In order of importance, it should let:

1. two people play each other online, on different computers;
2. a person play against an AI agent online: only `Deepening:mix`;
3. a person ask the AI for a hint.

What we agreed:
- An MVP first: no accounts. One player starts a game and sends a link; whoever opens it plays the other side.
- The interface is in English.
- The page talks to the game in small messages ("move a1c3" in, "the new position" out). The page then does not care where the engine runs.
- Taras sent Pascal 5 questions about his hosting on 2026-10-20, and Pascal answered the same day:
  1. His server is Apache 2.4 with PHP and MariaDB. No Python, so it stays easy to move to any cheap host. HTTP for now, HTTPS later. His NAS, for tests at home, is the same.
  2. He uploads by FTP; SSH is possible.
  3. We can use any subdomain of peyremorte.fr.
  4. In the 7th Guest, Stauf starts, as his site says; it does not matter to him. So it only changes the menu's default.
  5. The fifty-move rule is fine; in practice it never happened.
- So the engine and agents run in the browser with Pyodide, and a small PHP server passes the moves (see `adr/0005`). Pyodide was 1.7 times slower than CPython and chose the same moves.

What we know so far:
- Our engine and agents never import Pygame, so they run in Pyodide unchanged. The Pygame drawing does not carry over: the board is drawn again for the browser, in SVG.
- Game records are already JSON with moves in standard notation, so they work on a web page as they are.
- Homebrew no longer builds PHP for macOS 14, so the laptop has no PHP yet; W2 was checked on GitHub, on PHP 7.4.

Steps:
- [x] W1. The game in the browser. A script copies our Python files into `web/`; a Web Worker loads Pyodide and answers the page's messages (new game, legal moves, play a move). A plain board to click, for two people on one computer. Check: a pytest test sends the worker's messages through Node and compares the answers with the engine; we time how long the page takes to load.
- [x] W2. The game server in PHP: make a game with two secrets, take a move, give the moves after number n, each with the player who sent it. SQLite on the laptop. Check: pytest starts `php -S` and tries every request, including a wrong secret, an old or skipped move number and two moves sent at once. CI runs it on PHP 7.4.
- [ ] W3. Online play on Taras's laptop: one player makes a game and sends the link, the other opens it and plays. Each browser checks every move it gets. Reloading the page keeps your place in the game. Check: two browsers, then two computers on the same Wi-Fi.
- [ ] W4. The page in the microscope look: the round lens, the microbes, clone, jump and infect animations, the side panel with pawns, turn and moves. Check: screenshots at laptop and phone width.
- [ ] W5. Online on Pascal's site: a deploy script, a config file on the server for MariaDB, a test with Pascal before telling anyone. Check: a full game between Taras and Pascal on the real address.
- [ ] W6. Play against `Deepening:mix`: the agent thinks in its own worker, Undo and New stop it, the menu picks your colour and who starts. Check: a game against it in Chrome, Firefox and Safari, and the depth it reaches in 0.5 s.
- [ ] W7. Hints online, from `Deepening:mix`. Check: a hint in a game between two people and in a game against the AI.

## Later

- **Accounts, for the web version.** A player keeps one name across visits, sees their past games, and sees who is online to start a game with them, instead of sending a link. A rating could come after that.
- **Undo in an online game between two people.** Not in the MVP: it needs the other player to agree, so one asks and the other accepts or refuses.
- **A French interface, for the web version.** Pascal will likely share the game with French friends.
- **Tournaments on the website.** Unlikely: 500 games take minutes of CPU, on the server or in a visitor's browser. Tournaments stay in the terminal.
- Outside Ataxx engines (over the UAI protocol, which the `ataxx` package speaks) as stronger opponents.
- Blocked cells, as in tournament Ataxx.
- A bitboard, if the profiler shows Deepening or MCTS need it (see `adr/0003`).
- Thoughts: the score of the current position, and a chart of that score over the game.
- Watch: step back and rewind through the game.
