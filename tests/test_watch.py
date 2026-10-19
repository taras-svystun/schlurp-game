"""Watch: two AI agents play each other, with their thoughts. No real screen."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")  # no real window during tests

import subprocess
import sys
import time
from pathlib import Path

import pygame
import pytest

from schlurp.agents import Agent, GreedyAgent, RandomAgent, Thoughts
from schlurp.engine import Game, Move, Player, Position
from schlurp.records import load_game
from schlurp.ui.board_view import HEIGHT, WIDTH
from schlurp.ui.menu import MenuScreen
from schlurp.ui.thoughts_view import score_text, scores_by_cell, work_text
from schlurp.ui.watch import FASTEST, SLOWEST, WatchScreen, delay_at, value_for

BLUE, GREEN = Player.BLUE, Player.GREEN


@pytest.fixture(autouse=True)
def pygame_running():
    pygame.init()
    yield
    pygame.quit()


def watch(blue=None, green=None, delay=0.0) -> WatchScreen:
    return WatchScreen({BLUE: blue or GreedyAgent(1), GREEN: green or GreedyAgent(2)}, delay=delay)


def think(screen):
    """Let the agent to move think, and wait until it is done."""
    screen.update()
    screen.thinking.wait(timeout=2)


def next_move(screen):
    """Let the agent to move think and play, skipping the waiting."""
    moves = len(screen.game.moves)
    think(screen)
    screen.animation = None
    screen.update()
    assert len(screen.game.moves) == moves + 1


def press(screen, key):
    return screen.handle(pygame.event.Event(pygame.KEYDOWN, key=key))


def click(screen, point):
    return screen.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=point, button=1))


def test_the_agents_take_turns():
    screen = watch()
    next_move(screen)
    next_move(screen)
    movers = [position.to_move for position in screen.game.positions[:2]]
    assert movers == [BLUE, GREEN]


def test_the_thoughts_are_about_the_position_on_the_board():
    screen = watch()
    think(screen)
    thoughts = screen.thinking.thoughts
    assert screen.thinking.position == screen.game.position
    assert set(thoughts.scores) == set(screen.game.position.legal_moves())
    assert screen.status() == f"Blue (Greedy) chose {thoughts.move}"


def test_the_move_waits_until_the_thoughts_were_shown_for_the_delay():
    screen = watch(delay=0.2)
    think(screen)
    screen.update()
    assert screen.game.moves == []  # done thinking, but the thoughts are still on show
    time.sleep(0.25)
    screen.update()
    assert len(screen.game.moves) == 1


def test_the_delay_starts_when_the_last_move_has_landed():
    screen = watch(delay=0.3)
    think(screen)
    screen.update()
    time.sleep(0.31)
    screen.update()  # Blue plays, and its move lands in 0.3 s
    assert len(screen.game.moves) == 1 and screen.animating
    think(screen)  # Green is done at once, while Blue's move is still landing
    time.sleep(0.4)
    screen.update()
    assert len(screen.game.moves) == 1  # landed at 0.3 s, so Green's thoughts were shown for only 0.1 s
    time.sleep(0.25)
    screen.update()
    assert len(screen.game.moves) == 2


def test_pause_stops_the_game_and_space_resumes_it():
    screen = watch()
    press(screen, pygame.K_SPACE)
    think(screen)
    screen.update()
    assert screen.paused and screen.game.moves == []
    assert screen.status().startswith("Paused.")

    press(screen, pygame.K_SPACE)
    screen.update()
    assert not screen.paused and len(screen.game.moves) == 1


def test_step_plays_one_move_and_stays_paused():
    screen = watch()
    press(screen, pygame.K_s)
    think(screen)
    screen.update()
    assert len(screen.game.moves) == 1 and screen.paused

    think(screen)
    screen.update()
    assert len(screen.game.moves) == 1  # still paused: one step is one move


def test_the_speed_slider_sets_the_time_per_move():
    screen = watch(delay=1.0)
    rect = screen.speed.rect
    click(screen, rect.midleft)
    assert screen.move_delay == pytest.approx(SLOWEST)
    click(screen, rect.midright)
    assert screen.move_delay == pytest.approx(FASTEST)


def test_the_slider_moves_evenly_from_slow_to_fast():
    assert delay_at(0) == pytest.approx(SLOWEST)
    assert delay_at(1) == pytest.approx(FASTEST)
    assert delay_at(0.5) == pytest.approx((SLOWEST * FASTEST) ** 0.5)  # halfway is the middle of a volume knob
    for delay in [0.05, 0.3, 1.0, 5.0]:
        assert delay_at(value_for(delay)) == pytest.approx(delay)


def test_each_part_of_the_thoughts_has_a_checkbox():
    screen = watch()
    panel = screen.thoughts
    assert all(box.checked for box in panel.checkboxes)
    click(screen, panel.line_box.rect.center)
    assert not panel.line_box.checked and panel.scores_box.checked and panel.work_box.checked


def test_a_cell_shows_the_best_score_of_the_moves_landing_there():
    thoughts = Thoughts(
        Move.parse("c3"), scores={Move.parse("c3"): 1, Move.parse("a1c3"): 3, Move.parse("e5c3"): -2, Move.parse("d4"): 0}
    )
    assert scores_by_cell(thoughts) == {Move.parse("c3").target: 3, Move.parse("d4").target: 0}


def test_scores_and_work_are_short():
    assert [score_text(s) for s in [7, -2, 0, 0.25]] == ["+7", "-2", "0", "0.25"]
    assert work_text(Thoughts(Move(0), positions=26, depth=1), 0.0003) == "26 positions, depth 1, 300 µs"
    assert work_text(Thoughts(Move(0)), 0.00001).startswith("no search")


def test_a_finished_watch_game_is_saved(records_in_a_temporary_folder):
    screen = watch(GreedyAgent(1), RandomAgent(2))
    while not screen.game.is_over:
        next_move(screen)

    [path] = (records_in_a_temporary_folder / "games").iterdir()
    record = load_game(path)
    assert (record.blue, record.green) == ("Greedy", "Random")
    assert record.replay().positions == screen.game.positions


def test_n_starts_a_new_game_and_m_goes_back_to_the_menu():
    screen = watch()
    next_move(screen)
    press(screen, pygame.K_n)
    assert screen.game.moves == []

    menu = press(screen, pygame.K_m)
    assert isinstance(menu, MenuScreen)
    assert menu.choices == {BLUE: "Greedy", GREEN: "Greedy"}


def test_watch_needs_two_ai_agents_and_two_agent_objects():
    with pytest.raises(ValueError, match="both players"):
        WatchScreen({BLUE: GreedyAgent(), GREEN: None})
    agent = GreedyAgent()
    with pytest.raises(ValueError, match="two agent objects"):
        WatchScreen({BLUE: agent, GREEN: agent})


def test_drawing_every_moment_of_a_watch_game():
    class SlowAgent(Agent):
        def choose_move(self, position):
            time.sleep(0.05)
            return position.legal_moves()[0]

    surface = pygame.Surface((WIDTH, HEIGHT))
    screen = watch(GreedyAgent(1), SlowAgent())
    screen.draw(surface)  # before anyone thinks
    think(screen)
    screen.draw(surface)  # Greedy's scores on the board
    screen.animation = None
    screen.update()
    screen.draw(surface)  # Blue's move landing
    screen.animation = None
    screen.update()
    screen.draw(surface)  # SlowAgent thinking, no scores: "gives no move scores"
    press(screen, pygame.K_SPACE)
    screen.draw(surface)  # paused
    for box in screen.thoughts.checkboxes:
        box.checked = False
    screen.draw(surface)
    screen.game = Game(start=Position.setup("\n".join(["BBBBBBB"] * 7)))
    screen.thinking = None
    screen.draw(surface)  # game over


def test_every_watch_control_fits_in_the_window():
    screen = watch()
    window = pygame.Rect(0, 0, WIDTH, HEIGHT)
    font = screen.view.font_small
    for button in screen.buttons:
        assert window.contains(button.rect), button.label
        assert font.size("Resume (P)" if button is screen.pause_button else button.label)[0] < button.rect.width - 8
    for box in screen.thoughts.checkboxes:
        assert window.contains(box.rect)
    assert window.contains(screen.speed.rect)


def test_the_watch_command_refuses_an_unknown_agent():
    schlurp = Path(sys.executable).parent / "schlurp"
    result = subprocess.run([schlurp, "watch", "Greedy", "Nobody"], capture_output=True, text=True)
    assert result.returncode != 0
    assert "No agent called 'Nobody'" in result.stderr
