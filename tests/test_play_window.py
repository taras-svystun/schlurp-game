"""The Play window, without a real screen: clicks become the right moves."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")  # no real window during tests

import subprocess
import sys
import time

import pygame
import pytest

from schlurp.engine import CELLS, Game, Move, Player, Position, cell_index
from schlurp.ui.board_view import ANIMATION_SECONDS, HEIGHT, WIDTH, MoveAnimation, cell_at, cell_center
from schlurp.ui.play import PlayScreen, describe, movable_pawns, reachable

BLUE, GREEN = Player.BLUE, Player.GREEN


@pytest.fixture
def screen():
    pygame.init()
    yield PlayScreen()
    pygame.quit()


def click(screen, name):
    screen.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=cell_center(cell_index(name)), button=1))


def played(screen) -> list[str]:
    return [str(move) for move in screen.game.moves]


def test_a1_is_bottom_left_and_g7_top_right():
    a1, g1, a7 = cell_center(cell_index("a1")), cell_center(cell_index("g1")), cell_center(cell_index("a7"))
    assert a1[0] < g1[0] and a1[1] == g1[1]  # columns go left to right
    assert a7[1] < a1[1] and a7[0] == a1[0]  # row 7 is at the top


def test_cell_at_finds_every_cell_and_nothing_off_the_board():
    assert all(cell_at(cell_center(cell)) == cell for cell in range(CELLS))
    assert cell_at((5, 5)) is None
    assert cell_at((WIDTH - 5, HEIGHT // 2)) is None


def test_pick_a_pawn_then_clone(screen):
    click(screen, "a7")
    assert screen.selected == cell_index("a7")
    click(screen, "b6")
    assert played(screen) == ["b6"]
    assert screen.selected is None
    assert screen.game.position.to_move is GREEN


def test_pick_a_pawn_then_jump(screen):
    click(screen, "g1")
    click(screen, "e3")
    assert played(screen) == ["g1e3"]
    assert screen.game.position.at("g1") is None


def test_click_an_empty_cell_next_to_your_pawns_clones_at_once(screen):
    click(screen, "g2")
    assert played(screen) == ["g2"]


def test_click_the_picked_pawn_again_drops_it(screen):
    click(screen, "a7")
    click(screen, "a7")
    assert screen.selected is None
    assert played(screen) == []


def test_click_another_pawn_picks_that_one(screen):
    click(screen, "a7")
    click(screen, "g1")
    assert screen.selected == cell_index("g1")


def test_click_a_cell_the_pawn_cannot_reach_drops_it(screen):
    click(screen, "a7")
    click(screen, "e3")  # g1 could jump there, but a7 cannot, and there is no pawn next to it
    assert played(screen) == []
    assert screen.selected is None


def test_the_opponents_pawns_cannot_be_picked(screen):
    click(screen, "a1")
    assert screen.selected is None
    click(screen, "a2")  # next to Green's a1, but Blue is to move and has no pawn there
    assert played(screen) == []


def test_a_pawn_with_no_move_cannot_be_picked(screen):
    picture = """
        B B B . . . .
        B B B . . . .
        B B B . . . .
        . . . . . . .
        . . . . . . .
        . . . . . . .
        . . . . . . G
    """
    screen.game = Game(start=Position.setup(picture))
    # Every cell within 2 of a7 is taken, so it has no move. b6 can still jump to the d column.
    assert cell_index("a7") not in movable_pawns(screen.game.position)
    click(screen, "a7")
    assert screen.selected is None
    click(screen, "b6")
    assert screen.selected == cell_index("b6")


def test_reachable_cells_of_a_corner_pawn():
    targets = reachable(Position.start(), cell_index("a7"))
    assert {str(move) for move in targets.values()} == {"a6", "b6", "b7", "a7a5", "a7b5", "a7c5", "a7c6", "a7c7"}


def test_messages_describe_the_move():
    start = Position.start()
    assert describe(start, Move.parse("b6"), start.play(Move.parse("b6"))) == "Blue cloned to b6."
    assert describe(start, Move.parse("a7c5"), start.play(Move.parse("a7c5"))) == "Blue jumped from a7 to c5."


def test_a_pass_is_shown_in_the_message(screen):
    picture = """
        G B B . . . .
        B B B . . . .
        B B . . . . .
        . . . . . . .
        . . . . . . .
        . . . . . . .
        . . . . . . .
    """
    screen.game = Game(start=Position.setup(picture))
    click(screen, "c5")
    assert screen.message == "Blue cloned to c5. Green cannot move and passes."
    assert screen.status() == "Blue to move"


def test_the_end_of_the_game_is_shown_and_clicks_stop(screen):
    picture = """
        . . . . . . .
        . . . . . . .
        . . . . . . .
        . . . G . . .
        . . . . . . .
        . . . . . . .
        . . . . . B .
    """
    screen.game = Game(start=Position.setup(picture))
    click(screen, "f1")
    click(screen, "e3")
    assert screen.status() == "Blue wins, 2 to 0"
    click(screen, "e3")
    assert screen.selected is None


def test_n_starts_a_new_game(screen):
    click(screen, "b6")
    screen.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_n))
    assert played(screen) == []


def test_drawing_works_at_every_moment(screen):
    surface = pygame.Surface((WIDTH, HEIGHT))
    screen.draw(surface)
    click(screen, "a7")
    screen.hover = cell_center(cell_index("c5"))
    screen.draw(surface)
    click(screen, "c5")
    # Halfway through the animation, and after it.
    move = screen.game.moves[-1]
    screen.animation = MoveAnimation(screen.game.positions[-2], move, time.monotonic() - ANIMATION_SECONDS / 2)
    screen.draw(surface)
    screen.animation = MoveAnimation(screen.game.positions[-2], move, time.monotonic() - ANIMATION_SECONDS)
    screen.draw(surface)
    assert screen.wants_hand_cursor in (True, False)


def test_the_engine_never_loads_pygame_through_the_command():
    # `schlurp --help` must not need a window: Pygame is loaded only when a window opens.
    code = "import sys; sys.argv = ['schlurp', '--help']\nimport schlurp.cli\n" \
           "try:\n    schlurp.cli.main()\nexcept SystemExit:\n    pass\nsys.exit('pygame' in sys.modules)"
    assert subprocess.run([sys.executable, "-c", code], capture_output=True).returncode == 0
