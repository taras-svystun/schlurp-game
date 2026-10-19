# Own Python game engine, the `ataxx` package only as a reference

We write the Schlurp rules ourselves in plain Python instead of building on an existing library, because the point of this project is to understand the game and the AI code, and to keep the rules exactly as we agreed (see `0002`). OpenSpiel, which checked our Awalé engine, has no Ataxx. The only trusted reference we found is `ataxx` on PyPI (by kz04px, MIT, pure Python), so it becomes our test oracle, installed only for the tests and pinned to version 2.2.0, since its author says its rules may still change.

Our engine must agree with it in four ways:
- perft from the start position (the number of move sequences of each length): 16, 256, 6460, 155888 at depths 1–4, and 4752668 at depth 5 in a slower test;
- thousands of random games played side by side, compared after every move: the legal moves, the position, passes, the end of the game and the result;
- small positions worked out by hand, one rule at a time;
- properties that always hold: pawns plus empty cells always make 49, a clone adds exactly 1 pawn plus the infected ones, a jump only changes the colour of the infected ones.

Where our rules differ from the package's on purpose (it makes a pass an explicit move, we pass automatically; it counts a pass towards the fifty-move rule, we do not), the test translates or skips that case.

## Considered Options

- **OpenSpiel**: no Ataxx game.
- **`ataxx` as the engine**: readable, but its API and rules may change, its moves and passes do not match our rules, and we would not learn the rules by using it.
- **No reference, only hand-checked positions**: possible, but a bug in our understanding would be in both the code and the tests.
