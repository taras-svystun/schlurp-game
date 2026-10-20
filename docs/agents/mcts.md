# MCTS

Code: `schlurp/agents/mcts_agent.py`. Tests: `tests/test_mcts_agent.py`.

## The idea

Every agent so far needs a **heuristic**: a guess at who is winning in a position where the game is not over. AlphaBeta and Deepening are only as good as that guess.

MCTS (Monte Carlo tree search) guesses differently: **play the game to the end at random, many times, and count who won.** A random game to the end is a **playout**. If Blue wins 70 of 100 playouts from a position, the position probably looks good for Blue. No heuristic is needed, so the same agent works for any game whose rules it knows.

### From flat Monte Carlo to a tree

The simplest version, flat Monte Carlo, gives every legal move the same number of playouts and plays the move that won most often. It wastes most of its playouts on moves that are clearly bad, and it never looks at what the opponent will answer: a move can win most random games and still lose to the one good answer.

MCTS grows a **tree** instead. The top is the position on the board, and each child is the position after one move. Each playout adds one position to the tree, and each position in the tree remembers how many playouts went through it (`visits`) and how many points the player who moved there got (`wins`). Each playout has four steps:

1. **Selection.** From the top, go down the tree, each time to the child that looks best (the UCB score, below).
2. **Expansion.** At the first position that has a move never tried, try it and add the new position to the tree.
3. **Playout.** From there, play random moves until the game ends.
4. **Backpropagation.** Walk back up to the top. Every position on the way learns who won: 1 point for a win, 1/2 for a draw, 0 for a loss, for the player who moved into it.

Good moves get more playouts, so their part of the tree grows deeper, and there the opponent's answers get tried too. When the playouts or the time run out, MCTS plays **the move it tried most**, not the move with the best share of wins: a move tried 3 times and won 3 times may just have been lucky.

### UCB: good moves, but also the others now and then

The selection step must balance two wishes: try the moves that look good (to learn more about them), and try the moves that were tried only a few times (because their first playouts may have been unlucky). The UCB formula adds both:

```
UCB = wins / visits  +  c × √( ln(parent's visits) / visits )
```

- The first part is the child's **share of wins**, from 0 to 1.
- The second part is a **bonus** for being tried few times. It grows slowly as the parent is visited more (the logarithm) and shrinks fast as the child itself is visited more. So a move that looks bad still gets tried now and then.
- `c` is `EXPLORATION`, √2, the textbook value when the results are between 0 and 1.

## How the code works

`Node` is one position in the tree: `position`, the `move` that led here, `parent`, `children`, the `untried` legal moves, `visits` and `wins`.

```python
def grow_tree(self, position):
    root = Node(position)
    while root.untried or not self.is_done(root.visits, started):
        if self.should_stop():
            break
        node = root                                   # 1. Selection
        while not node.untried and node.children:
            node = self.select(node)
        if node.untried:                              # 2. Expansion
            move = node.untried.pop(self.rng.randrange(len(node.untried)))
            child = Node(node.position.play_legal(move), move, node)
            node.children.append(child)
            node = child
        end = self.playout(node.position)             # 3. Playout
        while node.parent is not None:                # 4. Backpropagation
            node.visits += 1
            node.wins += points(end, node.parent.position.to_move)
            node = node.parent
        root.visits += 1
    return root
```

- `root.untried` keeps the loop going until every legal move at the top was tried once, even after the time is up, so every move gets a score.
- A node counts points for `node.parent.position.to_move`: the player who chose to move into it. That is the player who compares it with its brothers in the selection step. A pass changes nothing here: `play_legal` passes automatically, so the player to move in the parent is still the one who made the move.
- `playout` plays `play_legal(self.rng.choice(moves))` until `legal_moves()` is empty, which is exactly when the game is over. Every game ends: a clone adds a pawn, so the board fills up, and the fifty-move rule stops a long run of jumps.
- `is_done` stops at the number of playouts (`MCTS:1000`) or the time (`MCTS:0.2s`, 0.5 s by default), whichever comes first. Undo or New stop it at once through `should_stop`, as for the other agents.

`think` then picks the child with the most visits (ties: the better share, then a random choice in `legal_moves()` order, so the same seed picks the same move) and fills `Thoughts`:

- `scores`: each move's share of wins. Watch shows them on the board with 2 decimals, `0.00` to `1.00`.
- `line`: the move, then the answer tried most after it, and so on, while that answer was tried more than once. One random game says nothing about what the players expect.
- `playouts`, `positions` (the tree and every move of every playout) and `depth` (the deepest position in the tree). Watch shows them under "Work done".

## An example on a real position

The game Greedy lost to Random (see [greedy.md](greedy.md)), after `a6 a1b3 a6c4 g7g5 g1e2`. Green to move has 14 legal moves. `g5e3` loses: Blue answers `c4d2` and infects both of Green's pawns.

| Playouts | Best move (visits, share) | `g5e3` (visits, share) | Blue's `c4d2` under `g5e3` |
|---|---|---|---|
| 400 | `g5f3` (45, 0.58) | 26, 0.38 | not found yet |
| 4,000 | `f6` | tried, still looks fine | 8 of 202 visits, share 1.00 |

- At 400 playouts MCTS does not play `g5e3`, but not because it saw `c4d2`. It just won fewer random games after it.
- At 4,000 playouts `c4d2` has been found, and every playout through it was a win for Blue (1.00). But it got only 8 of the 202 playouts under `g5e3`: Blue has about 30 answers there, the bonus keeps sharing the playouts among all of them, and one good answer among 30 needs many visits before it takes over.

## Why it is weak in Ataxx

Two reasons, and we measured both.

1. **Playouts are slow and few.** A playout is about 154 moves long and takes about 2.5 ms, so MCTS plays about 200 playouts in half a second. A position has 20 to 80 legal moves. 200 playouts spread over 40 moves is 5 random games per move: a coin toss.

2. **Random games barely see who is ahead.** This is the bigger reason. In one game against Greedy, Blue (MCTS) fell from 3 pawns against 2 to 1 pawn against 10. We played 400 random playouts from each position of that game and counted Blue's share of points:

   | After move | Blue's pawns | Green's pawns | Blue's share in random playouts |
   |---|---|---|---|
   | 1 | 3 | 2 | 0.51 |
   | 6 | 3 | 5 | 0.48 |
   | 8 | 2 | 7 | 0.49 |
   | 10 | 1 | 10 | 0.41 |

   With 1 pawn against 10, Blue still wins 41% of random games. Random players almost never finish anyone off: a lone pawn keeps cloning, the opponent jumps around at random, and 150 moves later the board is full and the count is a coin toss. So in a playout a big loss of pawns early in the game looks like almost nothing, and a few playouts per move cannot tell the 9-pawn difference from noise. Greedy sees it at once.

   This also explains the strange shares in Watch, like 0.89 for a quiet move in the opening: the move with the most visits is the one that got lucky in its first few random games.

Faster playouts alone would not fix this: twice the playouts still measure a signal of 0.41 against 0.5 through a lot of noise. The playouts need to know more about Ataxx.

## What tournaments show

With `--seed 31`, on 4 processes:

| A | B | Games | A's points | Pawns at the end, A minus B | Moves per game | Took |
|---|---|---|---|---|---|---|
| `MCTS:0.2s` | `Random` | 40 | **100%** | +13.4 | 155 | 3 min |
| `MCTS:0.2s` | `Greedy` | 100 | **1.0% ± 2.0%** | −9.1 | 13 | 27 s |
| `MCTS:0.2s` | `Deepening:0.2s` | 100 | **1.0% ± 2.0%** | −9.0 | 12 | 29 s |
| `MCTS:1s` | `Greedy` | 20 | 5.0% ± 9.8% | −9.0 | 12 | 22 s |

- **MCTS beats Random every time**: it does learn something from the playouts. Those games run to a full board, like random games.
- **Greedy beats it 99 games of 100**, and in 12 moves: about as fast as Greedy beats Random (11 moves). Against an agent that infects whenever it can, MCTS plays almost like Random, for the reasons above.
- **5 times more time does not help** (5% with 1 s per move, inside the noise of 20 games).
- Moving first did not matter here: the stronger agent won from both sides.

So plain MCTS is the weakest of our search agents. That is a known result for Ataxx: random playouts mean little in a game where one move can flip a lot of pawns. It is still worth having: it is the base for the improvements below, and it shows in Watch how a completely different kind of agent thinks.

## Ideas to make it stronger

- **Smarter playouts.** Play the playouts with a simple rule instead of at random, for example Greedy's (take the move with the best pawn difference, with some randomness). A playout then looks like a real game, so its result means something. It costs more per playout.
- **Cut the playouts short.** Play a few random moves, then score the position with a heuristic (`pawns` or `mix`) instead of playing to the end. Shorter playouts, many more of them, and a clear signal. This is how strong Ataxx MCTS programs work.
- **Pawn counts in `Position`** (see the review): every move of a playout counts the pawns again. This would help the two ideas above more than plain MCTS.

## What the tests check

- Every playout goes through the top and adds exactly one position to the tree; the same seed gives the same thoughts.
- Its thoughts: a share between 0 and 1 for every legal move, in board order, the number of playouts, an expected line that starts with its move and is legal.
- It plays the move it tried most; selection prefers the better share but sends a playout to a move tried much less.
- A playout ends the game; a win is 1 point, a draw 1/2, a loss 0.
- It takes a win in one move, and does not play `g5e3` in the example above.
- It stops when the time is up, tries every move once even with almost no time, stops at once when the move is no longer wanted, and plays whole games against Greedy.
- `MCTS:1000`, `MCTS:0.2s` and `MCTS:500:1s` set the playouts and the time limit; a depth-only or heuristic option is refused.
