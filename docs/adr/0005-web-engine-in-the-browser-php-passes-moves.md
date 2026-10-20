# The web version runs our Python in the browser, and a small PHP server passes the moves

Pascal's server, where the web version will live, is Apache 2.4 with PHP and a MariaDB database. It does not run Python, and Pascal wants to keep it that way, so the site stays easy to move to any cheap host. It is on plain HTTP for now; HTTPS will come later. His NAS, for tests at home, is the same. He uploads files by FTP, and SSH is possible.

So no Python program can run on the server, and nothing can keep a connection open there: Apache with PHP answers one request and forgets it, so WebSockets are out.

## The decision

1. **The engine and the agents run in the visitor's browser, with Pyodide** (CPython built for the browser). The page loads our own `schlurp/engine.py` and `schlurp/agents/`, unchanged. The rules stay in one place, the one tested against the `ataxx` package (see `adr/0001`), and every agent we write in Python works on the web without a rewrite.
2. **Python runs in a Web Worker**, not in the page itself, so the page never freezes while an agent thinks. The page and the worker talk in the small messages from the plan ("move a1c3" in, "the new position" out). Undo or New during an AI's turn stops the worker and starts a fresh one; that does in the browser what `adr/0004` does with threads.
3. **A small PHP program with a database only passes moves between the two players.** It makes a game and its two links, stores each move, and tells the other browser about it. The browser asks it about once a second whether there is a new move. For a turn-based game that is fast enough, and it works on any PHP host.
4. **The server checks whose turn it is, not the rules.** Each link holds a secret for one player, and the server takes a move only with the secret of the player to move and the right move number. Each browser checks every move it receives with our engine, and stops the game if the move is illegal. A cheater can only break their own game.
5. **The database is reached through PHP's PDO, in plain SQL that MariaDB and SQLite both accept.** MariaDB on Pascal's server, SQLite on Taras's laptop and in the tests, so we install no database server. The server's password lives in a config file on the server, never in git.
6. **The page is plain JavaScript and SVG, with no framework and no build tool.** A script copies our Python files next to it. Pyodide comes from the jsDelivr CDN at a fixed version.

## What we measured

On Taras's laptop (Apple M1), Pyodide 314.0.7 (Python 3.14.2, released 2026-09-14) under Node, which uses the same JavaScript engine as Chrome, against CPython 3.11 from the start position:

| | CPython 3.11 | Pyodide |
|---|---|---|
| perft(3) | 0.02 s | 0.03 s |
| `Deepening:mix`, depth 3 | 0.04 s | 0.07 s |
| `Deepening:mix`, depth 4 | 0.18 s | 0.32 s |
| `Deepening:mix`, 0.5 s per move | depth 4 | depth 4 |

Pyodide was about 1.7 times slower and chose the same moves. With a time limit that only means sometimes one depth less. Starting Pyodide took 1.1 s. Its files are about 13 MB, 6.3 MB compressed; a browser downloads them once and keeps them.

## Considered options

- **A Python server** (FastAPI with WebSockets) running our engine. Our first choice before Pascal's answers: it reuses all the code and checks every move itself. But his server does not run Python, and a separate paid server would go against his wish for cheap hosting.
- **The engine written again in JavaScript or TypeScript.** Faster to start, and probably several times faster to search (we did not measure it), but the rules and every agent would exist twice, and the JavaScript copy would need its own checks against `ataxx`. Pyodide's speed was good enough.
- **The rules checked by the server, in PHP.** A third copy of the rules, to stop cheating in friendly games between people who send each other a link.
- **Browsers talking directly (WebRTC).** Still needs a server to introduce them, and often fails behind home routers.
- **JSON files instead of a database.** Works too, but Pascal offers MariaDB, and accounts (in "Later") will want a database anyway.

## Things to remember

- The site is on HTTP. Some browser features need HTTPS: `crypto.randomUUID()` and `navigator.clipboard` among them. The secrets are made by PHP's `random_bytes`, and "Copy link" has a fallback. On HTTP the secrets in links travel in clear, which is fine for friendly games.
- If Pyodide ever needs to come from Pascal's server instead of the CDN, Apache must compress `.wasm` files, or the download grows from 6 to 13 MB.
