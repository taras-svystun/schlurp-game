# Heuristics

Code: `schlurp/agents/heuristics.py`. Tests: `tests/test_heuristics.py`. Read [alphabeta.md](alphabeta.md) first: a heuristic is what AlphaBeta asks when its look-ahead stops.

This is not a new agent. It is a new part for AlphaBeta: you pick a heuristic by name after a colon, like `AlphaBeta:mix` or `AlphaBeta:2:mix`, or build one from weights, like `AlphaBeta:2:safe=0.5:holes=-1`.

## The idea

AlphaBeta looks a few moves ahead, then stops and asks "how good is this position for me?". Until now the only answer was `pawns`: my pawns minus the opponent's. It sees how many pawns each player has, but not how they stand. Two positions with the same count can be very different: in one my pawns are packed and safe, in the other they are full of holes the opponent can jump into.

The plan named four things to look at. Each one is a **feature**: a number counted on the board, always "mine minus the opponent's".

| Feature | Name in agent names | What it counts | Why it might matter |
|---|---|---|---|
| `mobility` | `mobility` | my legal moves minus theirs | More choice, more chances. |
| `safe_pawns` | `safe` | my pawns with no empty neighbour, minus theirs | Only a pawn landing next to it can infect a pawn. With no empty cell around it, nothing can land there: it is safe for the next move. |
| `exposed` | `exposed` | empty cells next to my pawns that an enemy pawn can reach, minus theirs | Where the opponent can land next move and infect me. |
| `holes` | `holes` | empty cells with 4 or more of my pawns around them, minus theirs | A jump out of the middle of my group leaves such a hole. An enemy pawn landing there infects at least 4. |

A feature alone is not a heuristic. `weighted` adds features to `pawns`, each times a **weight**: how many pawns one unit of the feature is worth. With `holes: -1`, each hole in my group costs as much as one pawn. A negative weight means the feature is bad to have.

We did not guess the weights. Tournaments chose them.

## How the code works

```python
def safe_pawns(position, me):
    return _safe(position, me) - _safe(position, me.opponent)

def _safe(position, player):
    cells, mine = position.cells, player.value
    return sum(1 for cell in range(CELLS)
               if cells[cell] == mine and all(cells[n] != EMPTY for n in NEIGHBOURS[cell]))

def _holes(position, player):
    cells, mine = position.cells, player.value
    return sum(1 for cell in range(CELLS)
               if cells[cell] == EMPTY and sum(cells[n] == mine for n in NEIGHBOURS[cell]) >= HOLE_PAWNS)

def weighted(weights):
    def heuristic(position, me):
        value = pawns(position, me)
        for feature, weight in weights.items():
            value += weight * feature(position, me)
        return round(value, 6)
    return heuristic

HEURISTICS = {
    "pawns": pawns,
    "mobility": weighted({mobility: 0.03}),
    "safe": weighted({safe_pawns: 0.5}),
    "exposed": weighted({exposed: -0.5}),
    "holes": weighted({holes: -1}),
    "mix": weighted({safe_pawns: 0.5, holes: -1}),
}
```

Step by step:

- **Each feature** is two small functions: one counts for a player (`_safe`, `_holes`, ...), the other takes mine minus the opponent's. `NEIGHBOURS` and `JUMP_TARGETS` come from the engine, worked out once, so a feature never checks the edges of the board.
- **`weighted`** takes a dict `{feature: weight}` and builds a heuristic: a new function that starts from `pawns` and adds each feature times its weight. A function that makes a function looks strange at first. It is the same as writing `def mix(position, me): return pawns(...) + 0.5 * safe_pawns(...) - holes(...)` by hand, but each new mix is one line.
- **`round(value, 6)`**: 0.1 has no exact value in binary, so `0.1 * 3` gives `0.30000000000000004`. Without rounding, two positions worth the same could score differently, and the search would think one is better.
- **A won game must stay the best.** The search scores a won game `WIN = 1000` or more. If a guess could reach that, the search might prefer a nice-looking position to a real win. Mobility can go past 100 moves, so in step 8 `WIN` went from 100 to 1000. `weighted` refuses weights that could reach it (`mobility=2` could score 1617), and a test checks every heuristic in `HEURISTICS`.
- **`HEURISTICS`** gives each heuristic a name for `make_agent`. Without a name AlphaBeta still uses `pawns`. For experiments, `make_agent` also takes features with weights in the name: `AlphaBeta:2:safe=0.5:holes=-1` is `mix` at depth 2. That is how the tournaments below were run: each worker process builds its agent from the name alone.

**What a feature costs.** Each feature reads the whole board, and AlphaBeta asks the heuristic in every position at the bottom of the search, thousands of times per move:

| Feature | Time per position |
|---|---|
| `pawns` | 2 µs |
| `safe_pawns` | 22 µs |
| `holes` | 39 µs |
| `exposed` | 57 µs |
| `mobility` | 62 µs |

Playing one move costs about 16 µs. So `mix` makes AlphaBeta about 3 to 5 times slower at the same depth.

## How the tournaments chose the weights

All at depth 2, where a game takes seconds. Each step only kept what clearly helped.

**Stage 1: each feature alone, against plain `pawns`** (`AlphaBeta:2:<feature>=<weight>` against `AlphaBeta:2`, 100 games each, seed 11):

| Weight | A's points | Time per move |
|---|---|---|
| `safe=0.5` | **79.0% ± 8.0%** | 52 ms |
| `safe=1` | 77.5% ± 8.2% | 49 ms |
| `holes=-1` | **70.0% ± 9.0%** | 83 ms |
| `holes=1` | 21.5% ± 8.0% | 77 ms |
| `exposed=-0.5` | 62.0% ± 9.5% | 114 ms |
| `exposed=-1` | 40.0% ± 9.5% | 96 ms |
| `mobility=0.03` | 55.0% ± 9.7% | 122 ms |
| `mobility=0.1` (40 games, an earlier try) | 32.5% ± 14.3% | 105 ms |

- **Safe pawns help the most**, and they are the cheapest feature to count.
- **Holes help with a negative weight and hurt with a positive one.** The sign is the whole story: `holes=1` loses 4 games out of 5.
- **Exposed cells help only a little.** With weight −1 the agent becomes so afraid of exposed cells that it loses.
- **Mobility does not help** and is the slowest. With weight 0.1 it even made the agent jump more: jumps keep many moves open but add no pawn, and the games had more fifty-move draws.

**Stage 2: mixes, against the best single feature** (against `AlphaBeta:2:safe=0.5`, 200 games each, seed 12). A strong agent must be compared with a strong one, not with plain `pawns`:

| Mix | A's points | Time per move |
|---|---|---|
| `safe=0.5:holes=-1` | **62.7% ± 6.7%** | 110 ms |
| `safe=0.5:holes=-2` | 32.0% ± 6.4% | 97 ms |
| `safe=0.5:holes=-1:exposed=-0.25` | 54.5% ± 6.9% | 203 ms |

Adding holes to safe pawns helps, but only with the right weight: −2 makes the agent so busy closing holes that it loses. Exposed cells added nothing but time. So **`mix` is `safe=0.5` and `holes=-1`**.

**Stage 3: checking the winner with a new seed** (seed 13). Trying many weights finds some winners by luck, so the winner is played again before we believe it (see [random.md](random.md#what-tournaments-show)):

| A | B | Games | A's points | Time per move, A and B |
|---|---|---|---|---|
| `AlphaBeta:2:mix` | `AlphaBeta:2` | 200 | **71.8% ± 6.1%** | 113 ms, 16 ms |
| `AlphaBeta:3:mix` | `AlphaBeta:3` | 60 | **73.3% ± 11.3%** | 710 ms, 143 ms |
| `AlphaBeta:2:mix` | `AlphaBeta:3` | 100 | **22.0% ± 8.2%** | 87 ms, 191 ms |

- **`mix` is clearly stronger than `pawns` at the same depth**, with a new seed, at depth 2 and at depth 3.
- **But one more move of depth is worth more than a better guess.** `mix` at depth 2 loses 4 games out of 5 to plain `pawns` at depth 3, and still takes half the time per move. Looking ahead finds what really happens; a heuristic only guesses it.
- So is `mix` worth its cost at the same time per move? Step 9 answered it: with a time limit of 0.2 s, `mix` searches about one move less deeply and still wins 65.5% ± 6.5% against `pawns` (see [deepening.md](deepening.md#what-tournaments-show)).
- `mix` games are longer (80 moves at depth 2, against 59 for two plain agents), and 7 of 200 ended by the fifty-move rule: an agent that cares about safe pawns and holes sometimes prefers to shuffle by jumping rather than open its group.
- Moving first helped again: Blue won 113 games and Green 80 at depth 2, 38 and 22 at depth 3.

**What we use.** AlphaBeta and Deepening keep `pawns` unless you name another heuristic, so a plain name stays quick. The hints in Play come from `Deepening:mix`.

## An example on a real position

From a game between two Greedy agents. Green to move, with 7 pawns against Blue's 6:

```
. . . . . . G
. . . . . . .
. . . . . . .
. G . . . . .
G G . B B B .
G G . B B . .
G . . . . . B
```

At depth 2 the two heuristics choose differently:

| Move | `pawns` | `mix` |
|---|---|---|
| `b2d1` or `b3d1` (a jump that infects d2 and e2) | **−3** | −3 |
| `b1` (a clone) | −5 | **−1** |

`pawns` takes the jump. It sees Blue's answer `d3b2`, into the hole the jump leaves in Green's corner, and still finds it the best count: 3 pawns behind.

`mix` takes the clone `b1`. After Blue's best answer `c2` Green is 5 pawns behind, but `mix` sees more than the count: Green's a1 and a2 are safe, and Blue's group now has 3 holes that Green can reach. It bets that Green jumps into one of them next move and infects 4 or more: −5 pawns, +1 for 2 safe pawns, +3 for 3 enemy holes = −1.

Is it right? A deeper search with plain `pawns` agrees at depth 3 (`b1` +6, the jumps +4): `mix` at depth 2 sees what `pawns` sees only one move deeper. At depth 4, where Blue also answers that jump, `b1` is slightly worse again (−4 against −3). A heuristic is a guess about the moves the search did not look at, and no guess is always right. The tournaments say that this one is right more often than plain counting.

## What the tests check

- On hand-drawn positions: a hole, a safe pawn, and exposed cells are counted as described.
- Mobility equals the number of legal moves of each player.
- Every feature is mine minus the opponent's, and none goes past its largest value.
- `weighted` adds features times weights, rounded; weights that could reach a won game are refused, and no heuristic in `HEURISTICS` can reach it.
- Agent names with feature weights work, and wrong ones are refused.
