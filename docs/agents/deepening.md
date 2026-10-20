# Deepening

Code: `schlurp/agents/deepening_agent.py`. Tests: `tests/test_deepening_agent.py`. Read [alphabeta.md](alphabeta.md) first: Deepening is AlphaBeta with three things added.

## The idea

AlphaBeta has two weak spots.

1. **It tries moves in board order**, from a1 to g7. Alpha-beta skips the most when the best move is tried first, and board order is just luck.
2. **It has a fixed depth.** At depth 4 it may answer in 0.3 seconds in one position and take 9 in another. We cannot say "think for half a second", which is what a person playing against it wants.

Deepening fixes both with three ideas that work together.

### 1. Move ordering: try the most promising moves first

Which move is most promising, before we search it? Two cheap guesses:

- **The move that was best here last time.** If we already searched this position a little less deep, its best move then is very likely its best move now.
- **The move with the best pawn difference right after it**: Greedy's idea. A big infection often is the best move, and when it is not, the opponent's infection back often is the best answer.

The first guess needs an earlier search of the same position. That is the next idea.

### 2. Iterative deepening: 1 move ahead, then 2, then 3, ...

Instead of one search 4 moves deep, Deepening searches 1 move deep, then 2, then 3, then 4. This looks wasteful: why search 3 deep, then throw it away and search 4 deep?

Because each depth costs about **8 to 10 times** more than the one before (a position has 20 to 80 moves). So all the shallower searches together cost only about a tenth of the last one. And they pay for themselves: each search remembers the best move in every position it saw (`best_moves`), and the next search tries that move first, so the deep search gets a good order almost everywhere.

### 3. A narrow window at the top

AlphaBeta searches every one of our moves with the widest window, so each one gets its exact score. Deepening does not need that. It tries the best move of the last search first, and it is usually still the best. For every other move it only has to prove "this is worse", not "this is exactly −7". So the window for the other moves starts **just below the best score so far**. A move that is worse fails quickly and gets only an **upper bound**: "−7 or less". Watch shows it as `≤-7`.

Why "just below" and not "at" the best score? When several moves are equally good, AlphaBeta picks one of them at random. To do the same, Deepening must know every move that **ties** for the best. With the window starting at the best score, a tie would only get "this or less". Starting a hair lower (`TIE`, 0.0000001) gives every tie its exact score. That works because our scores never differ by less than 0.000001: every heuristic rounds to 6 decimals, and a won game is a whole number.

So at a fixed depth, Deepening **chooses exactly the moves AlphaBeta chooses**, from the same random seed, only faster. Its scores are the same for the best moves, and only upper bounds for the others.

### And the time limit

Now a time limit is easy. Deepening searches deeper and deeper, and when the time is up it stops in the middle of a search, throws that unfinished search away, and plays the best move of the **deepest search it finished**. The search 1 move deep always finishes, so it always has a move.

It also stops early when looking deeper cannot help:

- **More than a fifth of the time is gone.** The next depth costs 8 to 10 times the last one, so it would not finish. We measured it: of 71 depths started after a fifth of the time, 1 finished. Stopping saves the time instead.
- **Every line of play ended the game** before the depth ran out. A deeper search sees exactly the same.
- **The best move surely wins, or every move surely loses.** A deeper search finds the same win, or the same loss.

## How the code works

`DeepeningAgent` is a subclass of `AlphaBetaAgent`. It keeps `final_value` and the heuristic, and replaces `think` and `alphabeta`. It has two new methods: `search` for our moves at the top, and `ordered_moves`.

```python
def ordered_moves(self, position):
    mover = position.to_move
    children = [(move, position.play_legal(move)) for move in position.legal_moves()]
    self.positions += len(children)
    children.sort(key=lambda child: child[1].pawns(mover) - child[1].pawns(mover.opponent), reverse=True)
    best = self.best_moves.get(position)
    if best is not None:
        children.sort(key=lambda child: child[0] != best)
    return children
```

It plays every move once, sorts by the pawn difference after it (Greedy's order), then puts last time's best move in front. `sort` keeps the order of equal items, so the second sort only moves the best move to the front: `False` comes before `True`.

```python
def think(self, position):
    started = time.perf_counter()
    self.best_moves = {}
    depth = 0
    while self.depth is None or depth < self.depth:
        depth += 1
        if depth > 1 and self.time_limit is not None:
            self.deadline = started + self.time_limit
        try:
            scores, upper_bounds, lines = self.search(position, depth, me)
        except OutOfTime:
            break
        done = depth, scores, upper_bounds, lines
        if not self.reached_horizon or abs(max(scores.values())) >= WIN:
            break
        if self.time_limit is not None and time.perf_counter() - started > self.time_limit * LAST_START:
            break
    ...
    move = self.rng.choice([move for move in legal if scores[move] == best])
```

- The loop is iterative deepening. `best_moves` lives for the whole move, so each depth learns from the ones before.
- The deadline is set only from depth 2 on, so depth 1 always finishes.
- `alphabeta` checks the clock in every position and raises `OutOfTime` when the deadline has passed. The exception unwinds the whole unfinished search at once, and `done` still holds the last finished one.
- `reached_horizon` is set when any line stopped at depth 0 rather than at the end of the game. If none did, a deeper search would find the same.
- The random choice between equally good moves takes them in `legal_moves()` order, like AlphaBeta, so the same seed picks the same move.

```python
def search(self, position, depth, me):
    alpha = -INFINITY
    for move, child in self.ordered_moves(position):
        low = alpha - TIE
        value, line = self.alphabeta(child, depth - 1, me, low, INFINITY)
        scores[move], lines[move] = value, (move, *line)
        if value <= low:
            upper_bounds.add(move)
        if value > alpha:
            alpha = value
            self.best_moves[position] = move
```

This is the narrow window at the top: each move gets the window from just below the best score so far. A result at or below `low` is only a bound.

### A faster engine

The profiler showed that a fifth of the search went into `play` checking that each move is legal, though the search only plays moves from `legal_moves()`, and another fifth into reading `Player.value`, which Python makes slow. So the engine got `play_legal`, which skips the check (anything a person or an agent chooses still goes through `play`), and `ends_game` reads the pawn numbers from constants. Searches are 28% faster, and the tests against the `ataxx` package still pass.

## An example on a real position

The position from [greedy.md](greedy.md) where a jump to c6 leaves a hole. Blue to move, 73 legal moves:

| Depth | Best move | Score | Expected line | Upper bounds | Positions, Deepening | Positions, AlphaBeta |
|---|---|---|---|---|---|---|
| 1 | `d4c6` | +10 | `d4c6` | 69 of 73 | 73 | 73 |
| 2 | `d4c6` | +5 | `d4c6 b1` | 71 of 73 | 3,739 | 3,666 |
| 3 | `d4c6` | +10 | `d4c6 a6 b1` | 72 of 73 | 12,447 | 27,628 |
| 4 | `a4c6` | +2 | `a4c6 a4 b1 a3c1` | 70 of 73 | 274,341 | |

- At depth 2 ordering does not help yet: there was almost nothing to learn from depth 1. At depth 3 Deepening looks at 2.2 times fewer positions than AlphaBeta, though its count includes depths 1 and 2.
- At depth 4 the best move changes: Blue jumps from a4 instead of d4. One more move of look-ahead shows something depth 3 could not see, and only the deepest finished search is played.
- Almost every move gets only an upper bound. Proving "worse than `d4c6`" is much cheaper than finding an exact score.

On 16 positions from Greedy games, Deepening looked at 1.5 times fewer positions than AlphaBeta at depth 3, and 3.3 times fewer at depth 4. With the faster engine, depth 4 takes 0.65 seconds on average instead of AlphaBeta's 3.

How deep a time limit gets, on 13 positions from Greedy games:

| Agent | Depth reached | Average time |
|---|---|---|
| `Deepening:0.2s` | 3, sometimes 4 | 0.08 s |
| `Deepening:0.5s` (the default) | 3 or 4 | 0.41 s |
| `Deepening:1s` | 4, sometimes 5 | 0.66 s |
| `Deepening:1s:mix` | 4, sometimes 3 | 0.81 s |

`mix` costs about one move of depth at the same time.

## What tournaments show

With `--seed 21`, on 4 processes:

| A | B | Games | A's points | Time per move, A and B | Took |
|---|---|---|---|---|---|
| `Deepening:0.2s:mix` | `Deepening:0.2s` | 200 | **65.5% ± 6.5%** | 114 ms, 95 ms | 7 min |
| `Deepening:0.2s` | `AlphaBeta:3` | 100 | **70.5% ± 8.9%** | 93 ms, 111 ms | 3 min |
| `Deepening:3` | `AlphaBeta:3` | 40 | 57.5% ± 15.5% | 53 ms, 119 ms | 1 min |

- **At the same depth, Deepening is as strong as AlphaBeta and twice as fast.** The two agents choose the same moves from the same seed, but in a tournament each game gives them different seeds, so the games differ and the result is only about 50%: 57.5% ± 15.5% includes it.
- **A time limit beats a fixed depth.** With 0.2 s per move Deepening reaches depth 3 in most positions and 4 in the easy ones, and wins 70.5% against AlphaBeta at depth 3, while thinking less per move.
- **At the same time, `mix` beats `pawns`: 65.5% ± 6.5%.** Step 8 left this open: `mix` lost to `pawns` one move deeper, so was it worth its cost? With a time limit `mix` searches less deeply (about one move less, see the table above) and still wins. A better guess at depth 3 beats a plain count at depth 4, at least at 0.2 s.
- Moving first helped again: Blue won 117 games and Green 79 in the first tournament.
- Time-limited games cannot be repeated exactly: how deep the agent gets depends on how fast the laptop is at that moment, and with 4 games at once it heats up and slows down. The seed still fixes the openings and the tie-breaks. For a result that can be repeated exactly, give a depth instead of a time.

**What we use.** The Hint button in Play now asks `Deepening:mix`: the strongest agent we have, and it never thinks longer than half a second. `Deepening` with no options thinks for 0.5 s with `pawns`; `Deepening:mix` is stronger at the same time.

## What the tests check

- At depths 1, 2 and 3 it chooses the moves AlphaBeta chooses, with the same seed, with `pawns` and with `mix`; its exact scores are AlphaBeta's, and its upper bounds are really above the true scores. It plays the same whole game as AlphaBeta.
- Where a move wins at once it stops at depth 1 and calls the same moves best.
- At depth 3 it looks at fewer positions than AlphaBeta; worse moves get upper bounds; the order is the last best move, then the pawn difference.
- It stops when the time is up, looks deeper with more time, and still looks 1 move ahead with almost no time.
- It stops looking deeper when every line ends the game or it surely wins, and stops at once when the move is no longer wanted.
- `Deepening:4`, `Deepening:0.2s` and `Deepening:1s:mix:6` set the depth, the time limit and the heuristic; wrong ones are refused.
- `play_legal` gives the same position as `play` for every legal move of a random game.
