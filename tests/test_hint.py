"""The Hint button in Play, without a real screen."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")  # no real window during tests

import threading

import pygame
import pytest

from schlurp.agents import Agent, DeepeningAgent
from schlurp.engine import Game, Move, Player, Position, cell_index
from schlurp.ui.board_view import HEIGHT, WIDTH, cell_center
from schlurp.ui.play import KEYS, KEYS_TOP, PANEL_WIDTH, PlayScreen

BLUE, GREEN = Player.BLUE, Player.GREEN

COLONY = """
    . . . . . . .
    . . . . . . .
    . . G G . . .
    . . G . B . .
    . . G G . . .
    . . . . . . .
    B . . . . . G
"""


class FirstMoveAgent(Agent):
    def choose_move(self, position):
        return position.legal_moves()[0]


class SlowHintAgent(Agent):
    """Thinks until it is asked to stop, or the test lets it answer."""

    def __init__(self):
        super().__init__()
        self.may_answer = threading.Event()

    def choose_move(self, position):
        while not self.may_answer.wait(0.001) and not self.should_stop():
            pass
        return position.legal_moves()[0]


@pytest.fixture(autouse=True)
def pygame_running():
    pygame.init()
    yield
    pygame.quit()


def press(screen, key):
    return screen.handle(pygame.event.Event(pygame.KEYDOWN, key=key))


def click(screen, point):
    return screen.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=point, button=1))


def get_hint(screen):
    press(screen, pygame.K_h)
    screen.hint_thinking.wait(timeout=2)
    screen.update()


def colony_screen() -> PlayScreen:
    screen = PlayScreen(ai_move_delay=0)  # two people
    screen.game = Game(start=Position.setup(COLONY))
    return screen


def test_h_shows_the_move_deepening_would_play():
    screen = colony_screen()

    get_hint(screen)

    assert screen.hint == Move.parse("d4")
    assert screen.message == "Hint from Deepening:mix: clone to d4."
    assert screen.game.moves == []  # a hint only shows the move, it does not play it


def test_the_hint_button_does_the_same():
    screen = colony_screen()

    click(screen, screen.hint_button.rect.center)
    screen.hint_thinking.wait(timeout=2)
    screen.update()

    assert screen.hint == Move.parse("d4")


def test_the_hint_goes_away_after_a_move_and_after_undo():
    screen = colony_screen()
    get_hint(screen)
    click(screen, cell_center(cell_index("d4")))
    assert screen.hint is None

    get_hint(screen)  # Green's turn now
    assert screen.hint is not None
    press(screen, pygame.K_u)
    assert screen.hint is None


def test_no_hint_while_the_ai_is_to_move_or_the_game_is_over():
    screen = PlayScreen({BLUE: FirstMoveAgent(), GREEN: None}, ai_move_delay=0)
    assert not screen.can_ask_hint  # Blue's AI moves first
    press(screen, pygame.K_h)
    assert screen.hint_thinking is None

    screen.game = Game(start=Position.setup("\n".join(["BBBBBBB"] * 7)))
    assert screen.game.is_over and not screen.can_ask_hint


def test_asking_twice_does_not_start_a_second_hint():
    screen = colony_screen()
    screen.hint_agent = SlowHintAgent()
    press(screen, pygame.K_h)
    first = screen.hint_thinking

    press(screen, pygame.K_h)

    assert screen.hint_thinking is first
    screen.hint_agent.may_answer.set()


def test_undo_while_the_hint_is_thinking_cancels_it():
    screen = PlayScreen(ai_move_delay=0)
    screen.game.play("b6")
    screen.hint_agent = SlowHintAgent()
    press(screen, pygame.K_h)
    thinking = screen.hint_thinking

    press(screen, pygame.K_u)

    thinking.wait(timeout=2)
    assert thinking.is_done  # the hint agent saw should_stop() and gave up
    screen.update()
    assert screen.hint is None and screen.hint_thinking is None


def test_the_hint_agent_is_never_one_of_the_players():
    opponent = DeepeningAgent()
    screen = PlayScreen({BLUE: None, GREEN: opponent}, ai_move_delay=0)
    assert isinstance(screen.hint_agent, DeepeningAgent)
    assert screen.hint_agent is not opponent


def test_drawing_a_clone_hint_and_a_jump_hint_works():
    screen = colony_screen()
    surface = pygame.Surface((WIDTH, HEIGHT))
    for hint in ["d4", "a1c2"]:
        screen.hint = Move.parse(hint)
        screen.draw(surface)


def test_the_buttons_and_keys_fit_in_the_panel():
    screen = PlayScreen()
    window = pygame.Rect(0, 0, WIDTH, HEIGHT)
    buttons = [screen.undo_button, screen.new_game_button, screen.menu_button, screen.hint_button]
    for i, button in enumerate(buttons):
        assert window.contains(button.rect), button.label
        assert screen.view.font_small.size(button.label)[0] < button.rect.width - 8, button.label
        assert not any(button.rect.colliderect(other.rect) for other in buttons[i + 1 :])
    assert KEYS_TOP + 18 * len(KEYS) <= screen.undo_button.rect.top  # the keys never run into the buttons
    assert all(screen.view.font_small.size(line)[0] <= PANEL_WIDTH for line in KEYS)


class BrokenHintAgent(Agent):
    def choose_move(self, position):
        raise RuntimeError("no hint today")


def test_a_broken_hint_agent_shows_its_error_and_the_game_goes_on(capsys):
    screen = colony_screen()
    screen.hint_agent = BrokenHintAgent()
    get_hint(screen)
    assert screen.hint is None
    assert screen.message == "Hint crashed. RuntimeError: no hint today See the terminal."
    assert "Traceback" in capsys.readouterr().err
    assert screen.persons_turn
