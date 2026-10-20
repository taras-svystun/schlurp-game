"""The Deepening agent: AlphaBeta with move ordering, iterative deepening and a time limit."""

import threading
import time

import pytest

from schlurp.agents import AlphaBetaAgent, DeepeningAgent, GreedyAgent, RandomAgent, make_agent
from schlurp.agents.deepening_agent import TIME_LIMIT
from schlurp.agents.heuristics import HEURISTICS, WIN
from schlurp.engine import Game, Player, Position

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


def positions_from_games(count=3, at=(6, 18)):
    found = []
    for seed in range(count):
        game = Game()
        agents = {BLUE: GreedyAgent(seed), GREEN: GreedyAgent(seed + 100)}
        while not game.is_over:
            if len(game.moves) in at:
                found.append(game.position)
            game.play(agents[game.position.to_move].choose_move(game.position))
    return found


def assert_thinks_like_alphabeta(deepening, alphabeta, position):
    """The same move, the exact score for every move that is not a bound, and bounds that are really above."""
    mine, theirs = deepening.think(position), alphabeta.think(position)
    assert mine.move == theirs.move
    assert list(mine.scores) == list(theirs.scores)  # the same moves, in the same order
    for move, score in theirs.scores.items():
        if move in mine.upper_bounds:
            assert mine.scores[move] >= score  # "this or less": the true score is at most this
        else:
            assert mine.scores[move] == score


@pytest.mark.parametrize("depth", [1, 2, 3])
def test_at_a_fixed_depth_it_chooses_the_moves_alphabeta_chooses(depth):
    for seed, position in enumerate(positions_from_games()):
        assert_thinks_like_alphabeta(DeepeningAgent(seed, depth=depth), AlphaBetaAgent(seed, depth=depth), position)


def test_it_chooses_like_alphabeta_with_the_mix_heuristic_too():
    mix = HEURISTICS["mix"]
    for seed, position in enumerate(positions_from_games()):
        assert_thinks_like_alphabeta(
            DeepeningAgent(seed, depth=2, heuristic=mix), AlphaBetaAgent(seed, depth=2, heuristic=mix), position
        )


def test_it_chooses_like_alphabeta_where_the_game_ends():
    # Deepening stops at depth 1 once it sees a sure win, so its win scores 1000 (no depth left),
    # where AlphaBeta at depth 3 scores the same win 1002. The moves it calls best are the same.
    position = Position.setup(LAST_PAWN)
    mine, theirs = DeepeningAgent(0, depth=3).think(position), AlphaBetaAgent(0, depth=3).think(position)
    assert mine.move == theirs.move
    best_mine = {move for move, score in mine.scores.items() if score == max(mine.scores.values())}
    best_theirs = {move for move, score in theirs.scores.items() if score == max(theirs.scores.values())}
    assert best_mine == best_theirs


def test_plays_the_same_games_as_alphabeta():
    def moves(agent):
        game = Game()
        agents = {BLUE: agent, GREEN: RandomAgent(5)}
        while not game.is_over:
            game.play(agents[game.position.to_move].choose_move(game.position))
        return game.moves

    assert moves(DeepeningAgent(3, depth=2)) == moves(AlphaBetaAgent(3, depth=2))


def test_looks_at_fewer_positions_than_alphabeta_deep_down():
    deepening, alphabeta = 0, 0
    for position in positions_from_games(2, at=(18,)):
        deepening += DeepeningAgent(0, depth=3).think(position).positions
        alphabeta += AlphaBetaAgent(0, depth=3).think(position).positions
    assert deepening < alphabeta * 0.8


def test_worse_moves_get_only_an_upper_bound():
    [position] = positions_from_games(1, at=(18,))
    thoughts = DeepeningAgent(0, depth=3).think(position)
    assert thoughts.upper_bounds
    assert thoughts.move not in thoughts.upper_bounds
    best = thoughts.scores[thoughts.move]
    assert all(thoughts.scores[move] < best for move in thoughts.upper_bounds)


def test_tries_the_last_best_move_first_then_the_best_pawn_difference():
    [position] = positions_from_games(1, at=(18,))
    agent = DeepeningAgent(0, depth=1)
    me = position.to_move

    ordered = [move for move, _ in agent.ordered_moves(position)]
    differences = [position.play(move).pawns(me) - position.play(move).pawns(me.opponent) for move in ordered]
    assert differences == sorted(differences, reverse=True)

    agent.best_moves[position] = ordered[-1]
    assert [move for move, _ in agent.ordered_moves(position)][0] == ordered[-1]


def test_stops_when_the_time_is_up():
    for position in positions_from_games(2):
        started = time.perf_counter()
        DeepeningAgent(0, time_limit=0.05).think(position)
        assert time.perf_counter() - started < 0.15


def test_more_time_looks_deeper():
    [position] = positions_from_games(1, at=(18,))
    assert DeepeningAgent(0, time_limit=0.01).think(position).depth < DeepeningAgent(0, time_limit=1).think(position).depth


def test_even_with_almost_no_time_it_looks_one_move_ahead():
    thoughts = DeepeningAgent(0, time_limit=0.000001).think(positions_from_games(1, at=(18,))[0])
    assert thoughts.depth == 1
    assert thoughts.scores


def test_stops_looking_deeper_when_every_line_ends_the_game():
    # One empty cell: any move fills the board and ends the game, so depth 1 already sees everything.
    position = Position.setup("\n".join(["BBBBBBB"] * 3 + ["GGGGGGG"] * 3 + ["GGGGGG."]))
    thoughts = DeepeningAgent(0, time_limit=1).think(position)
    assert thoughts.depth == 1


def test_stops_looking_deeper_once_it_surely_wins():
    thoughts = DeepeningAgent(0, time_limit=1).think(Position.setup(LAST_PAWN))
    assert thoughts.depth == 1
    assert thoughts.scores[thoughts.move] == WIN


def test_stops_when_the_move_is_no_longer_wanted():
    agent = DeepeningAgent(0, depth=6)
    agent.stop = threading.Event()
    agent.stop.set()
    thoughts = agent.think(Position.start())
    assert thoughts.move in Position.start().legal_moves()
    assert thoughts.positions < 100


def test_thinks_for_half_a_second_unless_told_otherwise():
    agent = DeepeningAgent()
    assert (agent.depth, agent.time_limit) == (None, TIME_LIMIT) == (None, 0.5)


def test_make_agent_sets_a_depth_a_time_limit_or_both():
    assert (make_agent("Deepening:4").depth, make_agent("Deepening:4").time_limit) == (4, None)
    assert make_agent("Deepening:0.2s").time_limit == 0.2
    agent = make_agent("Deepening:1s:mix:6")
    assert (agent.depth, agent.time_limit, agent.heuristic) == (6, 1.0, HEURISTICS["mix"])


@pytest.mark.parametrize("name", ["Deepening:0s", "Deepening:-1s", "Deepening:1s:2s", "AlphaBeta:1s", "Deepening:fast"])
def test_make_agent_refuses_a_time_limit_it_cannot_use(name):
    with pytest.raises(ValueError):
        make_agent(name)


def test_needs_a_depth_of_at_least_1_and_a_time_above_0():
    with pytest.raises(ValueError):
        DeepeningAgent(depth=0)
    with pytest.raises(ValueError):
        DeepeningAgent(time_limit=0)
