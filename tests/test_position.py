"""The rules, one at a time, on small positions worked out by hand."""

import pytest

from schlurp.engine import JUMPS_FOR_DRAW, Move, Player, Position, cell_index, cell_name

BLUE, GREEN = Player.BLUE, Player.GREEN

START = """
    B . . . . . G
    . . . . . . .
    . . . . . . .
    . . . . . . .
    . . . . . . .
    . . . . . . .
    G . . . . . B
"""

# Blue to move can wipe out Green's last pawn with the jump f1e3.
LAST_GREEN_PAWN = """
    . . . . . . .
    . . . . . . .
    . . . . . . .
    . . . G . . .
    . . . . . . .
    . . . . . . .
    . . . . . B .
"""


def moves(position: Position) -> set[str]:
    return {str(move) for move in position.legal_moves()}


def test_cell_names():
    assert cell_name(0) == "a1"
    assert cell_name(6) == "g1"
    assert cell_name(42) == "a7"
    assert cell_name(48) == "g7"
    assert all(cell_index(cell_name(cell)) == cell for cell in range(49))
    with pytest.raises(ValueError):
        cell_index("h1")


def test_moves_are_written_in_ataxx_notation():
    assert str(Move(cell_index("c3"))) == "c3"
    assert str(Move(cell_index("c3"), cell_index("a1"))) == "a1c3"
    assert Move.parse("a1c3") == Move(cell_index("c3"), cell_index("a1"))
    assert Move.parse("c3") == Move(cell_index("c3"))
    with pytest.raises(ValueError):
        Move.parse("a1c")


def test_start_position():
    start = Position.start()
    assert start == Position.setup(START)
    assert start.at("a7") is BLUE and start.at("g1") is BLUE
    assert start.at("a1") is GREEN and start.at("g7") is GREEN
    assert start.pawns(BLUE) == start.pawns(GREEN) == 2
    assert start.to_move is BLUE
    assert Position.start(GREEN).to_move is GREEN


def test_a_position_prints_as_a_picture():
    assert str(Position.start()).splitlines() == [
        "B . . . . . G", ". . . . . . .", ". . . . . . .", ". . . . . . .",
        ". . . . . . .", ". . . . . . .", "G . . . . . B", "Blue to move",
    ]  # fmt: skip


def test_start_moves():
    # Each corner pawn has 3 clones and 5 jumps.
    assert moves(Position.start()) == {
        "a6", "b6", "b7", "a7a5", "a7b5", "a7c5", "a7c6", "a7c7",
        "f1", "f2", "g2", "g1e1", "g1e2", "g1e3", "g1f3", "g1g3",
    }  # fmt: skip


def test_clone_keeps_the_old_pawn():
    after = Position.start().play(Move.parse("b6"))
    assert after.at("a7") is BLUE and after.at("b6") is BLUE
    assert after.pawns(BLUE) == 3
    assert after.to_move is GREEN


def test_jump_empties_the_old_cell():
    after = Position.start().play(Move.parse("a7c5"))
    assert after.at("a7") is None and after.at("c5") is BLUE
    assert after.pawns(BLUE) == 2


def test_clones_onto_one_cell_are_one_move():
    position = Position.setup("""
        . . . . . . G
        . . . . . . .
        . . . . . . .
        . . . . . . .
        . . . . . . .
        . . . . . . .
        B B . . . . .
    """)
    # a2 and b2 touch both Blue pawns, but each is listed once.
    clones = sorted(str(m) for m in position.legal_moves() if not m.is_jump)
    assert clones == ["a2", "b2", "c1", "c2"]


def test_infect_turns_every_enemy_neighbour():
    position = Position.setup("""
        . . . . . . .
        . . . . . . .
        . . . . . . .
        . . G G G . .
        . . G . G . .
        . B G G G G .
        . . . . . . .
    """)
    after = position.play(Move.parse("b2d3"))
    # All 8 neighbours of d3 were Green and are now Blue.
    for name in ["c2", "d2", "e2", "c3", "e3", "c4", "d4", "e4"]:
        assert after.at(name) is BLUE, name
    # f2 is 2 cells from d3, so it is not infected.
    assert after.at("f2") is GREEN
    assert after.pawns(BLUE) == 9 and after.pawns(GREEN) == 1


def test_infect_in_the_corner():
    position = Position.setup("""
        . G . . . . .
        G G . . . . .
        . . B . . . .
        . . . . . . .
        . . . . . . .
        . . . . . . .
        . . . . . . G
    """)
    after = position.play(Move.parse("c5a7"))
    assert [after.at(name) for name in ["a7", "b7", "a6", "b6"]] == [BLUE] * 4
    assert after.at("c5") is None
    assert after.pawns(GREEN) == 1


def test_jump_targets_are_exactly_two_cells_away():
    position = Position.setup("""
        . . . . . . .
        . . . . . . .
        . . . . . . .
        . . . B . . .
        . . . . . . .
        . . . . . . .
        . . . . . . G
    """)
    targets = {str(m)[2:] for m in position.legal_moves() if m.is_jump}
    assert targets == {
        "b6", "c6", "d6", "e6", "f6", "b5", "f5", "b4", "f4", "b3", "f3", "b2", "c2", "d2", "e2", "f2",
    }  # fmt: skip


def test_illegal_moves_are_refused():
    position = Position.start().play(Move.parse("b6"))  # Green to move, with pawns on a1 and g7
    refused = {
        "c4": "a clone with no Green pawn next to it",
        "a1a4": "a jump of 3 cells",
        "a1b2": "a jump of 1 cell",
        "g1e1": "a jump of Blue's pawn",
    }
    for text, why in refused.items():
        assert not position.is_legal(Move.parse(text)), why
        with pytest.raises(ValueError):
            position.play(Move.parse(text))


def test_moves_onto_a_taken_cell_are_refused():
    position = Position.setup("""
        B B G . . . .
        . . . . . . .
        . . . . . . .
        . . . . . . .
        . . . . . . .
        . . . . . . .
        . . . . . . .
    """)
    assert not position.is_legal(Move.parse("c7"))  # a clone onto Green's pawn
    assert not position.is_legal(Move.parse("a7c7"))  # a jump onto Green's pawn


def test_a_player_who_cannot_move_passes():
    # Green's only pawn sits in the corner. Blue's clone on c5 takes the last empty cell within
    # 2 cells of it, so Green cannot move and Blue moves again.
    position = Position.setup("""
        G B B . . . .
        B B B . . . .
        B B . . . . .
        . . . . . . .
        . . . . . . .
        . . . . . . .
        . . . . . . .
    """)
    assert position.can_move(GREEN)
    after = position.play(Move.parse("c5"))
    assert not after.can_move(GREEN)
    assert after.to_move is BLUE
    assert not after.ends_game()


def test_a_set_up_position_passes_too():
    stuck_green = """
        G B B . . . .
        B B B . . . .
        B B B . . . .
        . . . . . . .
        . . . . . . .
        . . . . . . .
        . . . . . . .
    """
    assert Position.setup(stuck_green, to_move=GREEN).to_move is BLUE


def test_no_pawns_ends_the_game_at_once():
    after = Position.setup(LAST_GREEN_PAWN).play(Move.parse("f1e3"))
    assert after.pawns(GREEN) == 0
    assert after.ends_game()
    assert after.legal_moves() == []
    assert after.result().winner is BLUE
    assert after.result().score == (2, 0)
    assert after.result().ended_by == "no pawns"


def test_full_board_more_pawns_wins():
    # Blue has no pawn near g1, so Blue cannot move and Green is to move. Green fills the board.
    position = Position.setup("\n".join(["BBBBBBB"] * 3 + ["GGGGGGG"] * 3 + ["GGGGGG."]))
    assert position.to_move is GREEN
    assert position.result() is None
    after = position.play(Move.parse("g1"))
    assert after.ends_game()
    assert after.result().winner is GREEN
    assert after.result().score == (21, 28)
    assert after.result().ended_by == "full board"


def test_fifty_move_rule_is_a_draw():
    position = Position.setup(START, jumps_in_a_row=JUMPS_FOR_DRAW - 1)
    assert not position.ends_game()
    after = position.play(Move.parse("a7a5"))
    assert after.jumps_in_a_row == JUMPS_FOR_DRAW
    assert after.ends_game()
    assert after.legal_moves() == []
    assert after.result().winner is None
    assert after.result().score == (2, 2)
    assert after.result().ended_by == "fifty-move rule"


def test_a_clone_resets_the_jump_count():
    position = Position.setup(START, jumps_in_a_row=40)
    assert position.play(Move.parse("a7a5")).jumps_in_a_row == 41
    assert position.play(Move.parse("b6")).jumps_in_a_row == 0


def test_a_wipe_out_on_the_last_jump_still_wins():
    position = Position.setup(LAST_GREEN_PAWN, jumps_in_a_row=JUMPS_FOR_DRAW - 1)
    result = position.play(Move.parse("f1e3")).result()
    assert result.winner is BLUE
    assert result.ended_by == "no pawns"


def test_positions_never_change():
    start = Position.start()
    start.play(Move.parse("b6"))
    assert start == Position.start()
    with pytest.raises(AttributeError):
        start.to_move = GREEN
