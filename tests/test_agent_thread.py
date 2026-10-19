"""An agent never thinks in two threads at once, and a move that is no longer wanted is cancelled (docs/adr/0004)."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")  # no real window during tests

import threading
import time

import pygame
import pytest

from schlurp.agents import Agent
from schlurp.engine import Game, Player, cell_index
from schlurp.ui.agent_thread import AgentThread
from schlurp.ui.board_view import cell_center
from schlurp.ui.play import PlayScreen

BLUE, GREEN = Player.BLUE, Player.GREEN


class SearchingAgent(Agent):
    """Thinks like a long search: until the test lets it answer, or until it is asked to stop.

    It counts how many threads are inside it at once. With `listens=False` it ignores `should_stop`,
    like a search that never checks it.
    """

    name = "Searching"

    def __init__(self, listens=True):
        super().__init__()
        self.listens = listens
        self.may_answer = threading.Event()
        self.calls = self.inside = self.most_inside = self.stopped = 0
        self._count = threading.Lock()

    def choose_move(self, position):
        with self._count:
            self.calls += 1
            self.inside += 1
            self.most_inside = max(self.most_inside, self.inside)
        try:
            give_up = time.monotonic() + 5  # so a broken test never hangs
            while not self.may_answer.is_set() and time.monotonic() < give_up:
                if self.listens and self.should_stop():
                    self.stopped += 1
                    break
                time.sleep(0.001)
            return position.legal_moves()[0]
        finally:
            with self._count:
                self.inside -= 1


@pytest.fixture(autouse=True)
def pygame_running():
    pygame.init()
    yield
    pygame.quit()


def against(agent) -> PlayScreen:
    return PlayScreen({BLUE: None, GREEN: agent}, BLUE, ai_move_delay=0)


def click_cell(screen, name):
    screen.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=cell_center(cell_index(name)), button=1))


def press(screen, key):
    return screen.handle(pygame.event.Event(pygame.KEYDOWN, key=key))


def wait_until(condition, seconds=2.0):
    give_up = time.monotonic() + seconds
    while not condition() and time.monotonic() < give_up:
        time.sleep(0.001)
    return condition()


def test_undo_stops_the_search_that_is_no_longer_wanted():
    agent = SearchingAgent()
    screen = against(agent)
    click_cell(screen, "b6")
    screen.update()  # the AI starts thinking
    old = screen.thinking
    assert wait_until(lambda: agent.calls == 1)

    press(screen, pygame.K_u)

    old.wait(timeout=2)
    assert old.is_done
    assert agent.stopped == 1
    assert agent.stop is None  # the flag is taken away once the agent is done


def test_after_undo_the_new_search_waits_until_the_old_one_is_done():
    agent = SearchingAgent(listens=False)  # the worst case: it never checks should_stop
    screen = against(agent)
    click_cell(screen, "b6")
    screen.update()
    old = screen.thinking
    assert wait_until(lambda: agent.calls == 1)
    press(screen, pygame.K_u)
    click_cell(screen, "f2")  # the person plays something else
    screen.update()  # a new thread starts for the same agent
    new = screen.thinking

    time.sleep(0.05)
    assert agent.calls == 1  # the new thread waits: the old search still has the agent
    assert not old.is_done and not new.is_done

    agent.may_answer.set()
    new.wait(timeout=2)
    screen.update()
    assert agent.calls == 2
    assert agent.most_inside == 1  # never two threads inside the agent at once
    assert [str(move) for move in screen.game.moves][0] == "f2"  # the old answer was never played
    assert len(screen.game.moves) == 2


def test_a_thread_cancelled_while_waiting_never_calls_the_agent():
    agent = SearchingAgent(listens=False)
    busy = AgentThread(agent, Game())
    assert wait_until(lambda: agent.calls == 1)
    waiting = AgentThread(agent, Game())

    waiting.cancel()
    agent.may_answer.set()
    busy.wait(timeout=2)
    waiting.wait(timeout=2)

    assert agent.calls == 1
    assert waiting.is_done and waiting.thoughts is None and waiting.error is None


def test_cancelling_one_thread_does_not_stop_another_agent():
    first, second = SearchingAgent(), SearchingAgent()
    one, two = AgentThread(first, Game()), AgentThread(second, Game())
    assert wait_until(lambda: first.calls == second.calls == 1)

    one.cancel()
    one.wait(timeout=2)
    assert first.stopped == 1
    assert not two.is_done and second.stopped == 0

    second.may_answer.set()
    two.wait(timeout=2)
    assert two.thoughts is not None


@pytest.mark.parametrize("key", [pygame.K_n, pygame.K_m])
def test_new_game_and_menu_stop_the_search_too(key):
    agent = SearchingAgent()
    screen = against(agent)
    click_cell(screen, "b6")
    screen.update()
    old = screen.thinking
    assert wait_until(lambda: agent.calls == 1)

    press(screen, key)

    old.wait(timeout=2)
    assert old.is_done and agent.stopped == 1


def test_an_agent_is_never_asked_to_stop_outside_the_window():
    agent = SearchingAgent()
    assert not agent.should_stop()
    agent.may_answer.set()
    agent.choose_move(Game().position)  # as a tournament calls it
    assert agent.stopped == 0
