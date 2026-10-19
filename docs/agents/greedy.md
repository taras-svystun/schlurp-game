# Greedy

Code: `schlurp/agents/greedy_agent.py`. Tests: `tests/test_greedy_agent.py`.

## The idea

Greedy looks one move ahead. It tries each legal move, counts the pawns after it (its own minus the opponent's), and plays the move with the best difference. If several moves give the same difference, it picks one of them at random.

It never thinks about what the opponent does next. That is its whole strength and its whole weakness:

- **Strength:** it never misses a big infection. Random misses them all the time, so Greedy beats Random in 499 games out of 500.
- **Weakness:** it does not see the infection it gives away. It will take 3 pawns and leave a hole where the opponent takes 7 back.

Greedy is the first agent that *searches*, even if only one move deep. AlphaBeta (step 7) is the same idea, but it also looks at the opponent's answer, and at our answer to that, and so on.

Greedy also gives the hints in Play (the H key): it is the strongest agent we have for now.

## How the code works

```python
class GreedyAgent(Agent):
    name = "Greedy"

    def think(self, position: Position) -> Thoughts:
        me, enemy = position.to_move, position.to_move.opponent
        scores = {}
        for move in position.legal_moves():
            after = position.play(move)
            scores[move] = after.pawns(me) - after.pawns(enemy)
        best = max(scores.values())
        move = self.rng.choice([move for move, score in scores.items() if score == best])
        return Thoughts(move, scores, line=(move,), positions=len(scores), depth=1)
```

Step by step:

1. `me, enemy = ...`: remember who we are. After a move it is the other player's turn, so we must remember it before playing.
2. `position.play(move)` gives the position after that move, with the infections and a pass if needed. `Position` never changes, so trying a move does not touch the real game. We only look.
3. `after.pawns(me) - after.pawns(enemy)` is the score: how many pawns we are ahead after the move. It is the same as "how much the move gains", because the difference before the move is the same for every move. Thinking of the gain is easier:
   - a clone adds 1 pawn, and each infected pawn changes sides, which counts twice: one less for them, one more for us. So a clone that infects `k` pawns gains `1 + 2k`;
   - a jump adds no pawn, so a jump that infects `k` pawns gains `2k`.

   So **Greedy jumps only when the jump infects more than every clone.** With equal infections it always clones. This comes out of the counting by itself; nobody wrote a rule for it.
4. `best` is the highest score, and we keep every move that reaches it.
5. `self.rng.choice(...)` picks one of those at random. Why not `max(scores, key=scores.get)`? Because `max` returns the first best move in the list, and the list starts at a1. At the start all 6 clones score the same, and Greedy would always play `f1`. That is a bias with no reason behind it. `self.rng` is the agent's own seeded generator (see [random.md](random.md)), so the same seed still gives the same game.
6. Greedy writes `think`, not `choose_move`, because it has thoughts to show. Watch (step 6) will draw them:
   - `scores`: the pawn difference after each legal move;
   - `line=(move,)`: it looks only one move ahead, so the line it expects is just its own move;
   - `positions=len(scores)`: it looked at one position after each legal move;
   - `depth=1`: one move ahead.

   `Agent.choose_move` is built from `think`, so the tournament works without extra code.

It is fast: about 0.2–0.3 ms per move, because a position has 20–70 legal moves and each one is one `play`.

## An example: the best move is easy to see

Blue to move. Blue has 2 pawns, Green 6:

```
. . . . . . .
. . . . . . .
. . G G . . .
. . G . B . .
. . G G . . .
. . . . . . .
B . . . . . G
```

```python
>>> GreedyAgent(seed=0).think(position).move
Move(target=24, source=None)   # d4
```

The clone `d4` lands in the middle of Green's colony and infects all 5 neighbours: Blue 8, Green 1, a score of +7. Every other move scores 0 or less. Greedy plays `d4` every time; Random plays it 1 time in 26.

## An example: where Greedy goes wrong

From a game of Greedy against Greedy. Blue to move, Blue 11 pawns, Green 9:

```
. . . . . . G
. G . . . . .
G G G G . . .
B B B B . . .
G B B B . . .
G B B . . . .
G . . . . B B
```

Four moves share the best score, +10: jumps to c6 from `a4`, `b4`, `c4` or `d4`. Each lands on c6, just above Green's row on row 5, and infects the same 4 pawns: b6, b5, c5 and d5. For Greedy they are equal, so it picks at random. Here it picked `c4c6`:

```
. . . . . . G          After c4c6 the cell c4 is empty, with 7 Blue pawns around it.
. B B . . . .          Green jumps a2c4 (or a3c4, a5c4) and infects all 7:
G B B B . . .
B B . B . . .          Blue 7, Green 13.
G B B B . . .
G B B . . . .
G . . . . B B
```

Had it picked `d4c6`, the hole would be at d4, which no Green pawn can reach. Green's best answer would infect only 2 pawns: Blue 13, Green 8.

The same score now, but 13 − 8 = +5 instead of 7 − 13 = −6 one move later. Greedy cannot tell them apart, because the difference only shows after the opponent's answer. Two later steps fix this in two ways:

- **AlphaBeta (step 7)** looks at the opponent's answers, so it sees the −6 directly.
- **The "holes" heuristic (step 8)** sees that a jump leaves an empty cell next to many of your own pawns, without looking ahead.

## What tournaments show

`schlurp tournament Greedy Random --seed 1` (500 games, 0.3 seconds):

```
A wins 499 (99.8%), draws 0 (0.0%), loses 1 (0.2%).
A's points: 99.8% ± 0.4%
Pawns at the end, A minus B: +8.6 ± 0.3 on average.
Time per move: A 266 µs, B 12 µs.
Games ended by: full board 1, no pawns 499, fifty-move rule 0. 11 moves per game on average.
```

Greedy wipes Random out: almost every game ends with Random losing all its pawns, after only 11 moves. One pawn ahead in Ataxx often means infecting the whole enemy group next move.

The one game Random won shows the weakness above in its simplest form. After the random opening `a6 a1b3 a6c4 g7g5`, Greedy (Green) had a single pawn on g5, and Random's `g1e2` gave it a target. Greedy jumped `g5e3` and infected e2, so it had 2 pawns, both next to d2. Random's pawn on c4 could jump to d2, and did: `c4d2` infected both, and Green had no pawns left.

`schlurp tournament Greedy Greedy --seed 1` (500 games, 1.4 seconds):

```
A's points: 49.2% ± 4.4%
By player: Blue won 272, Green won 228, 0 draws.
Games ended by: full board 311, no pawns 189. 53 moves per game on average.
```

Even, as two copies of one agent must be. Blue won 54.4% of the games, just at the edge of the interval, so moving first may help a little. Random against Random showed nothing like it (253 to 247), so if it is real, it matters only when the players play well. We will look again with AlphaBeta.

## What the tests check

- On the colony above it plays `d4`, for every seed.
- The score of every legal move is the pawn difference after it, and the thoughts say depth 1, one position per move.
- At the start it picks among the 6 clones, about equally often, and never a jump.
- It jumps when the jump infects more than every clone.
- It plays only legal moves to the end of 10 games, and the same seed gives the same game.
