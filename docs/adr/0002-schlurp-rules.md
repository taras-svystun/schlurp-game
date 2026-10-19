# The Schlurp rules we play

We follow Schlurp as Pascal Peyremorte wrote it (version 2.21, read from its Delphi source), which is the 7th Guest Microscope puzzle, and take one rule from standard Ataxx to make sure every game ends.

- The board is 7 × 7, with no blocked cells.
- Blue starts on the top-left and bottom-right corners, Green on the other two. Blue moves first, unless the start menu says otherwise.
- A move is a **clone** (a new pawn on an empty neighbour, the old one stays) or a **jump** (a pawn moves to an empty cell exactly 2 cells away, and its old cell becomes empty). Then every enemy pawn next to the landing cell is **infected**.
- A player who cannot move **passes** automatically. A pass is not a move.
- The game ends when the board is full, when a player has no pawns (at once, even with empty cells left), or when neither player can move. Without blocked cells the last one cannot happen, but the engine still checks it.
- **Fifty-move rule** (from standard Ataxx, not in Peyremorte): when 100 moves in a row (50 by each player) are jumps, the game ends in a draw. Passes do not count.
- Otherwise the player with more pawns wins, and equal counts are a draw.
- Moves are written in standard Ataxx notation: columns a–g from left to right, rows 1–7 from bottom to top; a clone is its landing cell (`c3`), a jump is both cells (`a1c3`).

- Clones onto the same cell from different pawns are **one move**, because they give exactly the same position. Peyremorte writes a clone as "from → to", which makes them different moves; we follow standard Ataxx instead, so agents never search the same position twice and our move counts match the reference (see `0001`). In the window a person still clicks a pawn and then a cell.

## Why the fifty-move rule, and why a draw

Peyremorte has no such rule, so two players that only jump could play forever, and Watch and Tournament would hang. A clone always adds a pawn, so a position can only repeat during a run of jumps: limiting that run is enough to end every game. In 2000 random games no run of jumps was longer than 53 moves, so the rule only stops agents that shuffle on purpose. It ends in a draw, not a win for the player with more pawns, because otherwise a player ahead would learn to jump back and forth for 100 moves instead of finishing the game.

## Considered Options

- **Standard tournament Ataxx with blocked cells**: not the 7th Guest game. Kept for later.
- **Repetition ends the game** (as in our Awalé): needs the whole game history to check, and the fifty-move rule already ends every loop.
- **No limit at all**: games between agents could never end.
- **A clone as "from → to"** (as in Peyremorte): up to 3–4 moves for the same position in the middle game, so every search would do that work several times.
