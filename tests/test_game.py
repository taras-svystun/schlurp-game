"""Game: the whole game, its history, undo and the result."""

import subprocess
import sys

import pytest

from schlurp.engine import Game, Move, Player, Position

BLUE, GREEN = Player.BLUE, Player.GREEN


def test_a_new_game():
    game = Game()
    assert game.position == Position.start()
    assert game.positions == (Position.start(),)
    assert game.moves == []
    assert not game.is_over
    assert game.result is None
    assert Game(first=GREEN).position.to_move is GREEN


def test_play_takes_a_move_or_its_name():
    game = Game()
    game.play("b6")
    game.play(Move.parse("a1a3"))
    assert [str(m) for m in game.moves] == ["b6", "a1a3"]
    assert len(game.positions) == 3
    assert game.positions[1] == Position.start().play(Move.parse("b6"))


def test_undo():
    game = Game()
    game.play("b6")
    game.play("a2")
    game.undo()
    assert game.position == Position.start().play(Move.parse("b6"))
    assert [str(m) for m in game.moves] == ["b6"]
    game.undo()
    assert game.position == Position.start()
    with pytest.raises(ValueError):
        game.undo()


def test_copy_is_separate():
    game = Game()
    game.play("b6")
    copy = game.copy()
    copy.play("a2")
    copy.undo()
    copy.undo()
    assert [str(m) for m in game.moves] == ["b6"]
    assert len(game.positions) == 2


def test_a_finished_game_refuses_moves():
    picture = """
        . . . . . . .
        . . . . . . .
        . . . . . . .
        . . . G . . .
        . . . . . . .
        . . . . . . .
        . . . . . B .
    """
    game = Game(start=Position.setup(picture))
    game.play("f1e3")
    assert game.is_over
    assert game.result.winner is BLUE
    with pytest.raises(ValueError):
        game.play("e3e5")
    game.undo()
    assert not game.is_over


def test_the_engine_never_imports_pygame():
    # The window is just one front end: the rules must work without it (and in a web version later).
    code = "import sys, schlurp.engine; sys.exit('pygame' in sys.modules)"
    assert subprocess.run([sys.executable, "-c", code]).returncode == 0
