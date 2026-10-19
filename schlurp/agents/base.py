"""What every AI agent looks like from the outside."""

import random
from abc import ABC
from dataclasses import dataclass, field

from schlurp.engine import Game, Move, Position


@dataclass(frozen=True)
class Thoughts:
    """What an agent shows about how it chose its move. Watch will draw these next to the board.

    Only `move` is needed. An agent that does not look ahead (like Random) leaves the rest empty.
    """

    move: Move
    # The score of each legal move, for the player to move: higher is better.
    scores: dict[Move, float] = field(default_factory=dict)
    # The moves it expects next, starting with `move`, then the opponent's answer, and so on.
    line: tuple[Move, ...] = ()
    positions: int = 0  # how many positions it looked at
    depth: int = 0  # how many moves ahead it looked


class Agent(ABC):
    """Chooses a move in a position.

    Write one of the two methods:
    - `choose_move`, for an agent with nothing to show, like Random;
    - `think`, for an agent that can show its thoughts (move scores, the line it expects, the work it did).
    Each one is built from the other, so the window, Watch and Tournament can call either
    and any agent can play against any other.
    """

    name = "Agent"

    def __init__(self, seed: int | None = None):
        # Every agent has its own random generator, for agents that use chance (Random, ties between moves, MCTS).
        # Not the shared `random` module: the same seed then always gives the same moves,
        # so a game or a whole tournament can be repeated exactly.
        self.rng = random.Random(seed)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Each method calls the other, so an agent that writes neither would loop forever. Stop it early.
        if cls.choose_move is Agent.choose_move and cls.think is Agent.think:
            raise TypeError(f"{cls.__name__} must define choose_move or think")

    def choose_move(self, position: Position) -> Move:
        """Return one of `position.legal_moves()`.

        It is only called when the game is not over, so the player to move always has a move.
        It may run in a background thread, so it must not touch the window.
        """
        return self.think(position).move

    def think(self, position: Position) -> Thoughts:
        """Choose a move, like `choose_move`, and also say how it was chosen."""
        return Thoughts(self.choose_move(position))

    def think_in_game(self, game: Game) -> Thoughts:
        """Think about the position on the board in `game`. Tournament, Play and Watch call this one.

        Most agents only need the position, so this just calls `think`. An agent that also needs
        the moves before it (an outside engine that must replay the game, say) writes its own.
        """
        return self.think(game.position)
