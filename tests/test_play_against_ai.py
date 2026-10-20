"""Play against an AI agent, Undo, and the start menu, without a real screen."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")  # no real window during tests

import threading

import pygame
import pytest

from schlurp.agents import Agent, RandomAgent
from schlurp.engine import Player, cell_index
from schlurp.records import load_game
from schlurp.ui.board_view import HEIGHT, WIDTH, cell_center
from schlurp.ui.menu import PERSON, MenuScreen
from schlurp.ui.game_screen import PANEL_WIDTH, error_words, wrap
from schlurp.ui.play import PlayScreen
from schlurp.ui.watch import WatchScreen

BLUE, GREEN = Player.BLUE, Player.GREEN


class FirstMoveAgent(Agent):
    """A test agent that always plays the first of its legal moves, so the tests know what it will do."""

    name = "First"

    def choose_move(self, position):
        return position.legal_moves()[0]


class WaitingAgent(FirstMoveAgent):
    """Thinks until the test lets it answer, to test what happens while an AI is thinking."""

    def __init__(self):
        super().__init__()
        self.may_answer = threading.Event()

    def choose_move(self, position):
        self.may_answer.wait(timeout=5)
        return super().choose_move(position)


class BrokenAgent(Agent):
    name = "Broken"

    def choose_move(self, position):
        raise RuntimeError("this agent is broken")


@pytest.fixture(autouse=True)
def pygame_running():
    pygame.init()
    yield
    pygame.quit()


def against(agent, person=BLUE, first=BLUE) -> PlayScreen:
    return PlayScreen({person: None, person.opponent: agent}, first, ai_move_delay=0)


def let_ai_move(screen):
    screen.update()  # the agent starts thinking in its own thread
    screen.thinking.wait()
    screen.update()  # its move is played


def click_cell(screen, name):
    screen.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=cell_center(cell_index(name)), button=1))


def click(screen, point):
    return screen.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=point, button=1))


def press(screen, key):
    return screen.handle(pygame.event.Event(pygame.KEYDOWN, key=key))


def played(screen) -> list[str]:
    return [str(move) for move in screen.game.moves]


def test_the_ai_answers_the_persons_move():
    screen = against(FirstMoveAgent())
    click_cell(screen, "b6")
    assert screen.status() == "Green (First) is thinking..."
    let_ai_move(screen)
    # Legal moves are listed cell by cell from a1, and Green's own pawn on a1 comes first with its jumps.
    assert played(screen) == ["b6", "a1c1"]
    assert screen.message == "Green (First) jumped from a1 to c1."
    assert screen.status() == "Blue to move"


def test_the_ai_can_move_first():
    screen = against(FirstMoveAgent(), person=GREEN, first=BLUE)
    let_ai_move(screen)
    assert len(screen.game.moves) == 1
    assert screen.game.position.to_move is GREEN


def test_the_person_cannot_move_for_the_ai():
    screen = against(FirstMoveAgent(), person=GREEN, first=BLUE)
    click_cell(screen, "a7")
    click_cell(screen, "b6")
    assert played(screen) == []
    assert screen.selected is None


def test_the_ai_waits_a_moment_so_you_see_your_own_move_first():
    screen = PlayScreen({BLUE: None, GREEN: FirstMoveAgent()}, ai_move_delay=60)
    click_cell(screen, "b6")
    screen.update()
    screen.thinking.wait()
    screen.update()
    assert played(screen) == ["b6"]


def test_undo_between_two_people_takes_back_one_move():
    screen = PlayScreen()
    click_cell(screen, "b6")
    click_cell(screen, "b2")
    press(screen, pygame.K_u)
    assert played(screen) == ["b6"]


def test_undo_against_the_ai_goes_back_to_your_last_turn():
    screen = against(FirstMoveAgent())
    click_cell(screen, "b6")
    let_ai_move(screen)
    click_cell(screen, "f2")
    let_ai_move(screen)
    press(screen, pygame.K_u)
    assert played(screen) == ["b6", "a1c1"]
    assert screen.game.position.to_move is BLUE


def test_undo_while_the_ai_is_thinking_takes_back_your_move_and_drops_its_answer():
    agent = WaitingAgent()
    screen = against(agent)
    click_cell(screen, "b6")
    screen.update()  # the agent starts thinking
    press(screen, pygame.K_u)
    agent.may_answer.set()
    screen.update()
    assert played(screen) == []
    assert screen.thinking is None


def test_undo_does_nothing_before_your_first_move():
    screen = against(FirstMoveAgent(), person=GREEN, first=BLUE)
    let_ai_move(screen)
    press(screen, pygame.K_u)
    assert len(screen.game.moves) == 1


def test_undo_button():
    screen = PlayScreen()
    click_cell(screen, "b6")
    click(screen, screen.undo_button.rect.center)
    assert played(screen) == []


def test_a_broken_agent_shows_its_error_and_the_window_stays_open(capsys):
    screen = against(BrokenAgent())
    click_cell(screen, "b6")
    screen.update()
    screen.thinking.wait()
    screen.update()  # does not raise
    assert screen.status() == "Green (Broken) crashed."
    assert screen.message == "RuntimeError: this agent is broken See the terminal."
    assert "Traceback" in capsys.readouterr().err
    screen.update()
    assert screen.thinking is None  # it does not try again by itself
    screen.draw(pygame.Surface((WIDTH, HEIGHT)))


def test_undo_gives_a_broken_agent_another_try():
    screen = against(BrokenAgent())
    click_cell(screen, "b6")
    screen.update()
    screen.thinking.wait()
    screen.update()
    press(screen, pygame.K_u)
    assert screen.crashed is None
    assert screen.status() == "Blue to move"


def test_new_game_after_a_broken_agent_starts_clean():
    screen = against(BrokenAgent())
    click_cell(screen, "b6")
    screen.update()
    screen.thinking.wait()
    screen.update()
    screen.new_game()
    assert screen.crashed is None and screen.message == ""


def test_random_plays_a_whole_game_against_itself_through_the_window():
    screen = PlayScreen({BLUE: RandomAgent(seed=1), GREEN: RandomAgent(seed=2)}, ai_move_delay=0)
    while not screen.game.is_over:
        let_ai_move(screen)
    assert "wins" in screen.status() or "Draw" in screen.status()


def test_a_finished_game_is_saved_as_a_game_record(records_in_a_temporary_folder):
    screen = against(RandomAgent(seed=2), person=GREEN, first=GREEN)
    person = RandomAgent(seed=1)  # plays the person's moves through the screen
    while not screen.game.is_over:
        if screen.persons_turn:
            screen.play(person.choose_move(screen.game.position))
        else:
            let_ai_move(screen)

    [path] = (records_in_a_temporary_folder / "games").iterdir()
    record = load_game(path)
    assert (record.blue, record.green, record.first) == ("Random", PERSON, GREEN)
    assert record.replay().positions == screen.game.positions


def test_the_menu_starts_a_game_with_the_chosen_players():
    menu = MenuScreen()
    click(menu, menu.player_buttons[(BLUE, "Random")].rect.center)
    click(menu, menu.player_buttons[(GREEN, PERSON)].rect.center)
    click(menu, menu.first_buttons[GREEN].rect.center)
    screen = press(menu, pygame.K_RETURN)
    assert isinstance(screen, PlayScreen)
    assert isinstance(screen.players[BLUE], RandomAgent)
    assert screen.players[GREEN] is None
    assert screen.game.position.to_move is GREEN


def test_the_menu_starts_watch_for_two_ai_agents():
    menu = MenuScreen()
    click(menu, menu.player_buttons[(BLUE, "Greedy")].rect.center)
    click(menu, menu.player_buttons[(GREEN, "Greedy")].rect.center)
    screen = press(menu, pygame.K_RETURN)
    assert isinstance(screen, WatchScreen)
    assert screen.players[BLUE] is not screen.players[GREEN]  # two agents, each with its own random generator


def test_every_menu_button_fits_in_the_window():
    menu = MenuScreen()
    window = pygame.Rect(0, 0, WIDTH, HEIGHT)
    for button in [*menu.player_buttons.values(), *menu.first_buttons.values(), menu.start_button]:
        assert window.contains(button.rect), button.label
        assert menu.view.font_small.size(button.label)[0] < button.rect.width - 8, button.label
    menu.draw(pygame.Surface((WIDTH, HEIGHT)))


def test_m_goes_back_to_the_menu_with_the_same_players():
    screen = against(RandomAgent(), person=GREEN, first=GREEN)
    menu = press(screen, pygame.K_m)
    assert isinstance(menu, MenuScreen)
    assert menu.choices == {BLUE: "Random", GREEN: PERSON}
    assert menu.first is GREEN


def test_a_long_error_fits_above_the_moves_list(capsys):
    screen = PlayScreen()
    words = error_words(ValueError("a very long message " * 20))
    assert len(wrap(words, screen.view.font_small, PANEL_WIDTH)) <= 3
