# AlphaBeta

Code: `schlurp/agents/alphabeta_agent.py`, the heuristic in `schlurp/agents/heuristics.py`. Tests: `tests/test_alphabeta_agent.py`. Read [greedy.md](greedy.md) first: AlphaBeta is Greedy that also looks at the answers.

## The idea

Greedy looks one move ahead and never asks "and then what does the opponent do?". AlphaBeta asks it, and then asks what we do after that, and so on, `depth` moves deep (3 by default: my move, the answer, my next move).

### Minimax: the opponent plays well too

Picture every line of play as a tree. The position now is the root; each legal move is a branch to a new position; each answer is a branch from there. At depth 3 the tree has my moves, then every answer to each of them, then every move of mine after each answer.

At the bottom, where the search stops, we cannot know who will win, so we guess with a **heuristic**. By default it is `pawns`: my pawns minus the opponent's. Step 8 added better ones, see [heuristics.md](heuristics.md). Then we go back up the tree:

- in a position where **I** am to move, its value is the value of my **best** move: I choose;
- in a position where the **opponent** is to move, its value is the value of their best move, which is the **worst** for me: they choose, and I expect them to choose well.

The best and the worst, maximum and minimum, give the method its name: **Minimax**. A move's score is "how many pawns I will be ahead after `depth` moves if both of us play well".

A position where the game ends needs no guess: a win is worth `WIN = 1000` plus the depth left, a loss `-1000` minus the depth left, a draw 0. 1000 is more than any heuristic can give (a pawn difference is at most 49; step 8 added features that can reach a few hundred), so a won game always beats being ahead. The depth left makes a quick win better than a slow one: a win found after 1 move keeps 2 moves of depth and scores 1002, after 3 moves it scores 1000. (In step 7 `WIN` was 100; step 8 raised it.)

A pass needs nothing special. After a pass the same player moves again, so the search asks `position.to_move is me` at each position instead of assuming that players take turns.

### Alpha-beta: skip what cannot change the choice

Minimax tries every line, and most of that work is wasted. Think of choosing a move like this:

> I tried my move **a**: whatever the opponent answers, I end up at least 2 pawns ahead. **a** is worth +2.
> Now I try my move **b**. The opponent's first answer to **b** leaves me 3 pawns behind.

Do I need the opponent's other answers to **b**? No. **b** is already worth −3 or less, because the opponent picks the answer that is worst for me. Maybe another answer is even worse, but I do not care how bad **b** is: I have **a**, and **a** is better. So I stop looking at **b** and go on to **c**.

That is the whole idea: **as soon as a move is proved worse than one we already have, stop looking at it**. It is called **pruning**: whole branches of the tree are cut off. The chosen move and its score are exactly Minimax's, because we only skip lines that could never be played if both sides play their best. A test checks this against plain Minimax on real positions.

Every position in the search carries two numbers:

- **alpha**: what **I** can already get somewhere higher in the tree. If this position is worth alpha or less to me, I will not let the game come here: I play the other way.
- **beta**: what the **opponent** can already hold me to somewhere higher. If this position is worth beta or more to me, the opponent will not let the game come here.

Only a value between them can change a choice above, so:

- on **my** turn, as soon as one of my moves is worth **beta or more**, stop: the opponent avoids this position anyway;
- on **their** turn, as soon as one of their answers is worth **alpha or less** to me, stop: I avoid this position anyway.

## How the code works

```python
def think(self, position):
    me = position.to_move
    results = {}
    for move in position.legal_moves():
        results[move] = self.alphabeta(position.play(move), self.depth - 1, me, -INFINITY, INFINITY)
    scores = {move: value for move, (value, _) in results.items()}
    best = max(scores.values())
    move = self.rng.choice([move for move, score in scores.items() if score == best])
    return Thoughts(move, scores, (move, *results[move][1]), self.positions, self.depth)

def alphabeta(self, position, depth, me, alpha, beta):
    if position.ends_game():
        return self.final_value(position, me, depth), ()
    if depth == 0:
        return self.heuristic(position, me), ()
    if self.should_stop():
        raise SearchStopped
    our_turn = position.to_move is me
    best, best_line = (-INFINITY if our_turn else INFINITY), ()
    for move in position.legal_moves():
        self.positions += 1
        value, line = self.alphabeta(position.play(move), depth - 1, me, alpha, beta)
        if our_turn:
            if value > best:
                best, best_line = value, (move, *line)
            alpha = max(alpha, best)
        else:
            if value < best:
                best, best_line = value, (move, *line)
            beta = min(beta, best)
        if alpha >= beta:
            break
    return best, best_line
```

Step by step:

1. `think` tries each of our moves and asks `alphabeta` for the position after it, with one move less of depth.
2. Each of our moves gets the widest window, `-INFINITY` to `INFINITY`. So every move gets its exact score, not just "worse than the best": Watch shows true numbers, and equally good moves are found and chosen at random, like in Greedy. This costs some speed; the Deepening step will look at it again.
3. `alphabeta` first checks the two places where the search stops: the end of the game (a sure value) and depth 0 (the heuristic's guess). The end of the game comes first, so a won position at depth 0 still counts as won.
4. `should_stop()` is how Undo or New stops a search that is no longer wanted (see `docs/adr/0004`). The exception unwinds the whole search at once, and `think` returns any legal move, which nobody plays.
5. `our_turn` decides whether we look for the highest value or the lowest. Only a strictly better value replaces the best, so on a tie the first move in the list stays.
6. Each value that comes back moves our side of the window: alpha up on our turn, beta down on theirs. When `alpha >= beta`, the rest of the moves cannot matter, and `break` skips them. That `break` is all of alpha-beta; without it this is plain Minimax.
7. Together with the value, each level returns the **line**: the move that gave the best value, followed by the line below it. At the root that is the expected line of play that Watch shows, like `d4c6 b1 ...`.
8. `self.positions` counts every position the search makes; Watch shows it as the work done.

## An example: the hole Greedy cannot see

From [greedy.md](greedy.md): Blue to move, 11 pawns against 9.

```
. . . . . . G
. G . . . . .
G G G G . . .
B B B B . . .
G B B B . . .
G B B . . . .
G . . . . B B
```

Greedy scores the four jumps to c6 the same (+10): each infects b6, b5, c5 and d5. AlphaBeta at depth 2 also looks at Green's answer:

| Move | Greedy (depth 1) | AlphaBeta depth 2 | Green's best answer |
|---|---|---|---|
| `d4c6` | +10 | **+5** | `b1`: no Green pawn can reach the hole at d4 |
| `a4c6` | +10 | +3 | |
| `b4c6` | +10 | −3 | |
| `c4c6` | +10 | **−6** | `a2c4`: into the hole at c4, infecting all 7 Blue pawns around it |

AlphaBeta plays `d4c6`, and its expected line is `d4c6 b1`.

## An example: a move that loses everything

The one game Greedy lost to Random. After `a6 a1b3 a6c4 g7g5 g1e2`, Green to move:

```
B . . . . . .
. . . . . . .
. . . . . . G
. . B . . . .
. B . . . . .
. . . . B . .
. . . . . . .
```

Greedy jumped `g5e3` to infect e2, which scores −1 at depth 1, as good as any move. At depth 2 AlphaBeta sees Blue's answer `c4d2`, which infects both of Green's pawns and ends the game: `g5e3` scores −1000, a loss. It plays `f6` instead (−4: behind, but alive).

## How much pruning saves

At depth 3, on positions after 20 moves of Greedy games, AlphaBeta looked at 4.7 times fewer positions than plain Minimax: from 2 to 15 times fewer, depending on the position. The best case for alpha-beta is when the best move is tried first, because then every other move is cut off quickly. Our moves come in board order, from a1 to g7, so often the best move comes late. Trying the most promising moves first (**move ordering**) is part of step 9.

Time per move, measured on positions from Greedy games:

| Depth | Average | Slowest |
|---|---|---|
| 2 | 0.012 s | 0.02 s |
| 3 | 0.15 s | 0.4 s |
| 4 | 3 s | 9 s |

Each move of depth costs about 10 to 20 times more, because a position has 20 to 80 legal moves. So the default depth is 3: quick enough to play against and for hints, and depth 4 waits for step 9.

AlphaBeta at depth 3 is now the agent behind the Hint button in Play.

## What tournaments show

All with `--seed 1`, on 4 processes:

| A | B | Games | A's points | Pawns, A minus B | Time per move, A | Took |
|---|---|---|---|---|---|---|
| AlphaBeta:2 | Greedy | 500 | **92.4% ± 2.3%** | +11.0 | 14 ms | 43 s |
| AlphaBeta:3 | Greedy | 200 | **94.0% ± 3.3%** | +10.2 | 162 ms | 2 min |
| AlphaBeta:3 | AlphaBeta:2 | 200 | **89.5% ± 4.3%** | +10.8 | 189 ms | 5 min |

What they show:

- **Looking at the answer is worth a lot.** Depth 2 alone beats Greedy in 9 games out of 10. Greedy's whole weakness, holes and pawns left next to empty cells the opponent can reach, is exactly what one more move of look-ahead sees.
- **Depth 3 against Greedy looks hardly better than depth 2** (94.0% against 92.4%, and the intervals overlap). Both win almost every game, so there is little room left to show a difference: it is like comparing two adults by how often they beat a child at chess.
- **Head to head, depth 3 wins 9 games out of 10 against depth 2.** That is where the extra move shows. To compare two strong agents, play them against each other, not against a weak one.
- Games against Greedy are short (35 moves at depth 3, and two in three end with Greedy losing every pawn). Between two AlphaBeta agents they last longer (59 moves) and more often fill the board.
- **Moving first seems to help.** Blue won 276 of 500 games in AlphaBeta:2 against Greedy (55.2%), after 272 of 500 in Greedy against Greedy. Two runs in a row at about 55% make a small first-move advantage likely. Our tournaments swap the players for every opening, so it never favours one agent.

## What the tests check

- `pawns` is my pawns minus the opponent's.
- At depths 1, 2 and 3 every move gets exactly the score of plain Minimax with no pruning, on positions from real games.
- At depth 1 the scores are Greedy's.
- At depth 2 it sees the hole at c4 and the wipe-out after `g5e3`, the two examples above.
- A quick win scores higher than a slow one; a pass gives the turn back to the searcher.
- It looks at fewer positions than plain Minimax, its line is a real line of play, and ties are broken at random.
- It stops at once when the move is no longer wanted.
- `AlphaBeta:2` and `AlphaBeta:pawns:4` set the depth and the heuristic; wrong options are refused.
- `AlphaBeta:2` beats Greedy clearly in a small tournament.
