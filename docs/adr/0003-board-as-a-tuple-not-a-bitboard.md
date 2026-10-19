# The board is a tuple of 49 cells, not a bitboard

Ataxx has many more moves per turn than Awalé (16 at the start, often 50–80 in the middle game), so we measured before choosing how to store the board. On Taras's laptop (Apple M1, Python 3.11), with throwaway versions of both, each with immutable positions:

| | perft(5) from the start | random games |
|---|---|---|
| tuple of 49 cells | 1.26 s | 614 games/s |
| bitboard (two Python ints) | 0.90 s | 528 games/s |

The bitboard was only 1.4 times faster at perft and slower at random games: in Python most of the time goes into building the list of moves, one Python object per move, and bitboards do not change that. The tuple is much easier to read and debug, and the agents are a lesson, so we start with it.

Agents only use `Position`'s methods, never the tuple itself, so we can switch to a bitboard later without changing them. We look at this again, with a profiler, when Deepening and MCTS need speed: counting pawns and empty neighbours is where bitboards (`int.bit_count()`) may pay off.

## Considered Options

- **Bitboard from day one**: little faster, harder to read.
- **A list of 7 rows**: the same speed as the tuple, but neighbours need two indexes and border checks everywhere.
