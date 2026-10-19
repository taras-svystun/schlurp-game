"""Heuristics: functions that look at a position and say how good it is for one player.

A heuristic does not choose moves. A search (like AlphaBeta) calls it on the positions
at the end of its look-ahead, where it stops and has to guess.
Each one is "mine minus the opponent's", so it is positive when the position is good for `me`.
"""

from collections.abc import Callable

from schlurp.engine import Player, Position

Heuristic = Callable[[Position, Player], float]


def pawns(position: Position, me: Player) -> int:
    """My pawns minus the opponent's: how many pawns I am ahead right now. From -49 to 49."""
    return position.pawns(me) - position.pawns(me.opponent)


# Every heuristic a search agent can use, by the name that goes after a colon: "AlphaBeta:3:pawns".
HEURISTICS: dict[str, Heuristic] = {
    "pawns": pawns,
}
