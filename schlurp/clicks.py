"""What a click on a cell can do: which pawns can move, and where one pawn can go. For any front end, with no drawing."""

from schlurp.engine import EMPTY, JUMP_TARGETS, NEIGHBOURS, Move, Position


def movable_pawns(position: Position) -> set[int]:
    """The cells of the pawns of the player to move that have at least one move."""
    me, pawns = position.to_move.value, set()
    for move in position.legal_moves():
        if move.source is not None:
            pawns.add(move.source)
        else:
            pawns.update(n for n in NEIGHBOURS[move.target] if position.cells[n] == me)
    return pawns


def reachable(position: Position, pawn: int) -> dict[int, Move]:
    """The empty cells one pawn can reach, with the move for each: a clone next to it, a jump 2 cells away."""
    if position.ends_game():
        return {}
    cells = position.cells
    targets = {n: Move(n) for n in NEIGHBOURS[pawn] if cells[n] == EMPTY}
    targets.update({t: Move(t, pawn) for t in JUMP_TARGETS[pawn] if cells[t] == EMPTY})
    return targets
