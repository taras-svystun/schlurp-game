"""The MCTS agent: Monte Carlo tree search."""

import threading
import time

import pytest

from schlurp.agents import GreedyAgent, MCTSAgent, make_agent
from schlurp.agents.mcts_agent import TIME_LIMIT, Node, points
from schlurp.engine import Game, Move, Player, Position

BLUE, GREEN = Player.BLUE, Player.GREEN

# Green's last pawn on d4: every move landing next to it wins at once.
LAST_PAWN = """
    B . . . . . .
    . . . . . . .
    . . . . . . .
    . . . G . . .
    . . . . B . .
    . . . . . . .
    . . . . . . .
"""


def after(moves: str) -> Position:
    game = Game()
    for move in moves.split():
        game.play(move)
    return game.position


def test_every_playout_goes_through_the_top_and_adds_one_position():
    agent = MCTSAgent(seed=0, playouts=200)
    root = agent.grow_tree(Position.start())
    assert root.visits == 200
    assert sum(child.visits for child in root.children) == 200
    nodes = list(agent.walk(root))
    assert len(nodes) == 1 + 200  # the top, and one new position per playout


def test_the_same_seed_gives_the_same_thoughts():
    assert MCTSAgent(seed=3, playouts=100).think(Position.start()) == MCTSAgent(seed=3, playouts=100).think(Position.start())


def test_its_thoughts():
    position = Position.start()
    thoughts = MCTSAgent(seed=0, playouts=300).think(position)
    assert list(thoughts.scores) == position.legal_moves()  # every move, in board order
    assert all(0 <= share <= 1 for share in thoughts.scores.values())
    assert thoughts.playouts == 300
    assert thoughts.line[0] == thoughts.move
    assert thoughts.depth >= 2
    assert thoughts.positions > 300  # the tree, and every move of every playout


def test_plays_the_move_it_tried_most():
    agent = MCTSAgent(seed=1, playouts=300)
    root = agent.grow_tree(Position.start())
    most = max(child.visits for child in root.children)
    assert MCTSAgent(seed=1, playouts=300).think(Position.start()).move in {
        child.move for child in root.children if child.visits == most
    }


def test_the_expected_line_follows_the_answers_tried_most():
    agent = MCTSAgent(seed=2, playouts=400)
    root = agent.grow_tree(Position.start())
    move = max(root.children, key=lambda child: child.visits).move
    line = agent.expected_line(root, move)
    position = Position.start()
    for step in line:
        assert position.is_legal(step)
        position = position.play(step)


def test_selection_prefers_good_moves_but_tries_the_others_now_and_then():
    root = Node(Position.start())
    good, bad = Node(Position.start(), Move.parse("b6"), root), Node(Position.start(), Move.parse("a7a5"), root)
    root.children = [good, bad]
    good.visits, good.wins = 10, 8.0
    bad.visits, bad.wins = 10, 2.0
    root.visits = 20
    assert MCTSAgent(seed=0).select(root) is good
    # Once the good move has been tried a lot more, the bonus sends a playout to the other one.
    good.visits, good.wins, root.visits = 1000, 800.0, 1010
    assert MCTSAgent(seed=0).select(root) is bad


def test_a_playout_goes_to_the_end_of_the_game():
    end = MCTSAgent(seed=0).playout(Position.start())
    assert end.ends_game()


def test_points_for_a_win_a_draw_and_a_loss():
    won = Position.setup("B" * 7 + "\n" + "\n".join(["." * 7] * 6))
    assert (points(won, BLUE), points(won, GREEN)) == (1.0, 0.0)
    draw = Position.setup("B . . . . . G\n" + "\n".join(["......."] * 6), jumps_in_a_row=100)
    assert points(draw, BLUE) == points(draw, GREEN) == 0.5


def test_takes_a_win_in_one_move():
    position = Position.setup(LAST_PAWN)
    for seed in range(3):
        move = MCTSAgent(seed=seed, playouts=300).choose_move(position)
        assert position.play(move).result().winner is BLUE


def test_avoids_the_move_that_loses_every_pawn():
    # The game Greedy lost to Random: Green's g5e3 lets Blue's c4d2 infect both its pawns.
    # Its share of wins can still look fine: under g5e3 Blue has about 30 answers, and 400 playouts are too few
    # to find c4d2 among them (see docs/agents/mcts.md). But the move is tried less, so it is not played.
    position = after("a6 a1b3 a6c4 g7g5 g1e2")
    for seed in range(3):
        assert MCTSAgent(seed=seed, playouts=400).choose_move(position) != Move.parse("g5e3")


def test_stops_when_the_time_is_up():
    started = time.perf_counter()
    MCTSAgent(seed=0, time_limit=0.05).think(after("b6 a1c3"))
    assert time.perf_counter() - started < 0.3  # a playout may run over the time a little


def test_even_with_almost_no_time_it_tries_every_move_once():
    position = after("b6 a1c3")
    thoughts = MCTSAgent(seed=0, time_limit=0.000001).think(position)
    assert set(thoughts.scores) == set(position.legal_moves())
    assert thoughts.playouts == len(position.legal_moves())


def test_stops_when_the_move_is_no_longer_wanted():
    agent = MCTSAgent(seed=0, playouts=100_000)
    agent.stop = threading.Event()
    agent.stop.set()
    thoughts = agent.think(Position.start())
    assert thoughts.move in Position.start().legal_moves()
    assert thoughts.playouts == 0


def test_plays_whole_games():
    game = Game()
    agents = {BLUE: MCTSAgent(seed=0, playouts=30), GREEN: GreedyAgent(0)}
    while not game.is_over:
        move = agents[game.position.to_move].choose_move(game.position)
        assert game.position.is_legal(move)
        game.play(move)


def test_thinks_for_half_a_second_unless_told_otherwise():
    agent = MCTSAgent()
    assert (agent.playouts, agent.time_limit) == (None, TIME_LIMIT) == (None, 0.5)


def test_make_agent_sets_the_playouts_a_time_limit_or_both():
    assert (make_agent("MCTS:1000").playouts, make_agent("MCTS:1000").time_limit) == (1000, None)
    assert make_agent("MCTS:0.2s").time_limit == 0.2
    agent = make_agent("MCTS:500:1s")
    assert (agent.playouts, agent.time_limit) == (500, 1.0)


@pytest.mark.parametrize("name", ["MCTS:0", "MCTS:mix", "MCTS:1s:2s", "MCTS:0s", "MCTS:safe=1"])
def test_make_agent_refuses_what_mcts_cannot_use(name):
    with pytest.raises(ValueError):
        make_agent(name)


def test_needs_at_least_1_playout_and_a_time_above_0():
    with pytest.raises(ValueError):
        MCTSAgent(playouts=0)
    with pytest.raises(ValueError):
        MCTSAgent(time_limit=0)
