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
