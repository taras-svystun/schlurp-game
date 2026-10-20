"""Heuristics: functions that look at a position and say how good it is for one player.

A heuristic does not choose moves. A search (like AlphaBeta) calls it on the positions
at the end of its look-ahead, where it stops and has to guess.

`pawns` counts only the pawns on the board. The features below look at how they stand.
Each one is "mine minus the opponent's", so it is positive when there is more of it on my side.
A feature alone is not a heuristic: `weighted` adds features to `pawns`, each with a weight
that says how many pawns one unit of it is worth. A negative weight means the feature is bad to have.
"""

from collections.abc import Callable

from schlurp.engine import CELLS, EMPTY, JUMP_TARGETS, NEIGHBOURS, WITHIN_TWO, Player, Position

Heuristic = Callable[[Position, Player], float]

# What a search scores a won game: more than any heuristic can give, so a sure win beats any guess.
# 1000, not 100: mobility can be more than 100 moves. `weighted` refuses weights that could reach it.
WIN = 1000

# An empty cell with this many of my pawns around it is a hole: an enemy pawn landing there infects them all.
HOLE_PAWNS = 4


def pawns(position: Position, me: Player) -> int:
    """My pawns minus the opponent's: how many pawns I am ahead right now. From -49 to 49."""
    return position.pawns(me) - position.pawns(me.opponent)


def mobility(position: Position, me: Player) -> int:
    """My legal moves minus the opponent's, whoever is to move: how much choice each player has.

    One clone per empty cell next to my pawns, and one jump per pawn and empty cell 2 away.
    """
    return _moves(position, me) - _moves(position, me.opponent)


def safe_pawns(position: Position, me: Player) -> int:
    """My pawns with no empty neighbour, minus the opponent's.

    A pawn is infected only by a pawn landing next to it, so with no empty cell around it, nothing can
    land there: it cannot be infected on the next move.
    """
    return _safe(position, me) - _safe(position, me.opponent)


def exposed(position: Position, me: Player) -> int:
    """Empty cells next to my pawns that an enemy pawn can reach, minus the same for the opponent.

    These are the cells where the opponent can land next move and infect some of my pawns.
    """
    return _exposed(position, me) - _exposed(position, me.opponent)


def holes(position: Position, me: Player) -> int:
    """Empty cells with HOLE_PAWNS or more of my pawns around them, minus the same for the opponent.

    A jump out of the middle of my group leaves such a hole. An enemy pawn landing there infects them all.
    """
    return _holes(position, me) - _holes(position, me.opponent)


def _moves(position: Position, player: Player) -> int:
    cells, mine = position.cells, player.value
    count = 0
    for cell in range(CELLS):
        if cells[cell] == EMPTY:
            count += any(cells[n] == mine for n in NEIGHBOURS[cell])  # one clone, from any of my pawns
        elif cells[cell] == mine:
            count += sum(cells[t] == EMPTY for t in JUMP_TARGETS[cell])
    return count


def _safe(position: Position, player: Player) -> int:
    cells, mine = position.cells, player.value
    return sum(
        1 for cell in range(CELLS) if cells[cell] == mine and all(cells[n] != EMPTY for n in NEIGHBOURS[cell])
    )


def _exposed(position: Position, player: Player) -> int:
    cells, mine, theirs = position.cells, player.value, player.opponent.value
    return sum(
        1
        for cell in range(CELLS)
        if cells[cell] == EMPTY
        and any(cells[n] == mine for n in NEIGHBOURS[cell])
        and any(cells[near] == theirs for near in WITHIN_TWO[cell])
    )


def _holes(position: Position, player: Player) -> int:
    cells, mine = position.cells, player.value
    return sum(
        1
        for cell in range(CELLS)
        if cells[cell] == EMPTY and sum(cells[n] == mine for n in NEIGHBOURS[cell]) >= HOLE_PAWNS
    )


# The largest each feature can be, for the test that no heuristic reaches a won game's score.
LARGEST = {pawns: CELLS, mobility: CELLS * 16, safe_pawns: CELLS, exposed: CELLS, holes: CELLS}


def weighted(weights: dict[Callable[[Position, Player], int], float]) -> Heuristic:
    """A heuristic: `pawns`, plus each feature times its weight.

    With `{mobility: 0.1}`, 10 more moves than the opponent are worth as much as 1 more pawn.
    Refuses weights so big that a position could look as good as a won game (see WIN).
    """
    largest = LARGEST[pawns] + sum(abs(weight) * LARGEST[feature] for feature, weight in weights.items())
    if largest >= WIN:
        raise ValueError(f"These weights could score a position {largest:g}, as much as a won game ({WIN}): use smaller ones")

    def heuristic(position: Position, me: Player) -> float:
        value = pawns(position, me)
        for feature, weight in weights.items():
            value += weight * feature(position, me)
        # 0.1 has no exact value in binary, so 0.1 * 3 gives 0.30000000000000004. Rounding makes two positions
        # that are worth the same get exactly the same score, so they are a real tie.
        return round(value, 6)

    heuristic.weights = weights  # so a test can check that no position looks as good as a won game
    return heuristic


# The features by the names used in agent names, like "AlphaBeta:2:mobility=0.1".
FEATURES = {"mobility": mobility, "safe": safe_pawns, "exposed": exposed, "holes": holes}

# Every heuristic a search agent can use, by the name that goes after a colon: "AlphaBeta:3:mobility".
# The weights come from tournaments, see docs/agents/heuristics.md.
HEURISTICS: dict[str, Heuristic] = {
    "pawns": pawns,
    # One feature each, with the best weight we tried for it alone.
    "mobility": weighted({mobility: 0.03}),
    "safe": weighted({safe_pawns: 0.5}),
    "exposed": weighted({exposed: -0.5}),
    "holes": weighted({holes: -1}),
    # The best mix we found. Mobility and exposed cells did not make it stronger, only slower.
    "mix": weighted({safe_pawns: 0.5, holes: -1}),
}
