# Random

Code: `schlurp/agents/random_agent.py`. Tests: `tests/test_random_agent.py`.

## The idea

Random does not think at all. It looks at the legal moves and picks one, each with the same chance.

It is still useful. It is the baseline: any agent that cannot beat Random clearly is not really playing. It is also a quick opponent for testing the window and, from step 4, the tournament.

## How the code works

```python
class Agent(ABC):
    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)


class RandomAgent(Agent):
    name = "Random"

    def choose_move(self, position: Position) -> Move:
        return self.rng.choice(position.legal_moves())
```

- `Agent` is the interface every agent follows (`schlurp/agents/base.py`). An agent writes one of two methods: `choose_move`, which returns just the move, or `think`, which returns the move with its thoughts (move scores, the line it expects, positions looked at, depth). Each is built from the other, so the window, Watch and Tournament work with any agent. Random has nothing to show, so it writes only `choose_move`.
- `position.legal_moves()` already knows all the rules: one clone per empty cell next to your pawns, and every jump. The player to move always has a move until the game ends, because the engine passes for them. So Random can never play an illegal move, and it does not need to know the rules itself.
- `self.rng` is the agent's own random generator. Every agent gets one from `Agent`, because later agents (ties between equal moves, MCTS) use chance too. We do not use the shared `random` module, for two reasons:
  - **Repeatable games.** `RandomAgent(seed=1)` always plays the same moves in the same positions. If a game shows a bug, we can play it again exactly. A tournament will give every agent its own seed, so one seed repeats a whole tournament.
  - **No hidden links.** With the shared module, one agent's choices would change the other agent's choices.
- `seed=None` (the default, used by the start menu) means a different game every time.
- In the window, the agent thinks in a background thread (`schlurp/ui/agent_thread.py`), so the window keeps drawing. Random takes about 20 microseconds, but later agents will think for seconds.

## An example

Blue to move:

```
. . . . . . .
. . . . . . .
. . G G . . .
. . G . B . .
. . G G . . .
. . . . . . .
B . . . . . G
```

Blue has 26 legal moves: 9 clones and 17 jumps. One of them is far better than the others: the clone `d4` lands in the middle of Green's colony and infects all 5 of its neighbours. Blue goes from 2 pawns against 6 to 8 against 1. Every other move leaves Blue between 4 pawns behind and even.

Any person would play `d4`. Random plays it 1 time in 26. This is exactly what the next agent, Greedy (step 6), fixes: it looks one move ahead and takes the move with the best pawn difference.

There is a second, quieter weakness. A pawn has up to 8 cells to clone to, but up to 16 to jump to, and clones onto one cell from several pawns are one move. So most legal moves are jumps: 10 of the 16 at the start, 17 of the 26 above. Random picks moves, not kinds of moves, so **77% of its moves are jumps**. A jump adds no pawn and leaves a hole behind, and holes are where the opponent lands to infect you.

When there is only one legal move, Random plays it, like everyone else. Below, every cell next to Blue's only pawn is taken, and only a5 is free to jump to:

```
B G G G G G G
G G G G G G G
. G G G G G G
G G G G G G G
G G G G G G G
G G G G G G G
G G G G G G G
```

## Random against Random

A quick check with the engine, before the tournament exists (step 4): 2000 games from the start position, Blue always moving first, each agent with its own seed.

- Blue won 1016, Green 984, no draws. With two equal players, luck alone puts Blue's wins within 1000 ± 45 in 95% of such runs, so moving first does not seem to matter much under random play.
- A game lasted 184 moves on average, from 5 to 317. 1836 games ended with a full board and 164 with a player losing all their pawns. None reached the fifty-move rule.
- The winner was 7.3 pawns ahead at the end on average.
- 20 microseconds per move, playing the move included.

## What the tests check

- It plays only legal moves, in 10 whole games.
- When there is one legal move, it plays that move.
- From the start position, 1600 choices give each of the 16 moves about 100 times (a fair choice).
- The same seeds give the same game, and other seeds give a different game.
