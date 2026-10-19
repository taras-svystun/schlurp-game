"""Rules every agent follows, whatever its algorithm."""

import subprocess
import sys

import pytest

from schlurp.agents import Agent, RandomAgent, Thoughts, make_agent
from schlurp.engine import Game, Move, Position


def test_agents_never_import_pygame():
    # The engine and the agents must work without a window, e.g. in a tournament or a web version.
    code = "import sys, schlurp.agents; sys.exit('pygame' in sys.modules)"
    assert subprocess.run([sys.executable, "-c", code]).returncode == 0


def test_an_agent_that_only_chooses_a_move_thinks_with_no_scores():
    thoughts = RandomAgent(seed=1).think(Position.start())
    assert thoughts.move in Position.start().legal_moves()
    assert thoughts.scores == {}
    assert thoughts.line == ()
    assert thoughts.positions == thoughts.depth == 0


def test_an_agent_that_only_thinks_can_also_just_choose_a_move():
    class ThinkingAgent(Agent):
        def think(self, position):
            return Thoughts(move=Move.parse("b6"), scores={Move.parse("b6"): 1.0})

    assert ThinkingAgent().choose_move(Position.start()) == Move.parse("b6")


def test_in_a_game_an_agent_thinks_about_the_position_on_the_board():
    class LastMoveAgent(Agent):
        def think(self, position):
            return Thoughts(move=position.legal_moves()[-1])

    game = Game()
    game.play("b6")
    assert LastMoveAgent().think_in_game(game) == LastMoveAgent().think(game.position)


def test_an_agent_must_write_choose_move_or_think():
    with pytest.raises(TypeError, match="choose_move or think"):

        class EmptyAgent(Agent):
            pass


def test_make_agent_builds_an_agent_by_its_name():
    agent = make_agent("Random", seed=1)
    assert isinstance(agent, RandomAgent)
    assert agent.name == "Random"


@pytest.mark.parametrize("name", ["Nobody", "random", "Random:3", "Random:"])
def test_make_agent_refuses_a_name_it_does_not_know(name):
    with pytest.raises(ValueError):
        make_agent(name)
