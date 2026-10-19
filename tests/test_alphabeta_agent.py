"""The AlphaBeta agent and the `pawns` heuristic."""

import threading

import pytest

from schlurp.agents import AlphaBetaAgent, GreedyAgent, RandomAgent, make_agent
from schlurp.agents.alphabeta_agent import DEPTH, WIN
from schlurp.agents.heuristics import pawns
from schlurp.engine import Game, Move, Player, Position
from schlurp.tournament import mean_and_margin, run_tournament

BLUE, GREEN = Player.BLUE, Player.GREEN

# From a game of Greedy against Greedy (see docs/agents/greedy.md): four jumps to c6 infect the same 4 pawns,
# but jumping from c4 leaves a hole that Green fills to infect 7, and jumping from d4 leaves one Green cannot reach.
HOLE = """
    . . . . . . G
    . G . . . . .
    G G G G . . .
    B B B B . . .
    G B B B . . .
    G B B . . . .
    G . . . . B B
"""


def minimax(position: Position, depth: int, me: Player) -> float:
    """Plain Minimax with no pruning, the reference AlphaBeta must agree with. Too slow to be an agent."""
    if position.ends_game():
        return AlphaBetaAgent.final_value(position, me, depth)
    if depth == 0:
        return pawns(position, me)
    values = [minimax(position.play(move), depth - 1, me) for move in position.legal_moves()]
    return max(values) if position.to_move is me else min(values)


def positions_from_games(count: int, moves: int, seed: int = 0) -> list[Position]:
    """Positions after `moves` moves of games between two Greedy agents."""
    found = []
    for game_seed in range(seed, seed + count):
        game = Game()
        agents = {BLUE: GreedyAgent(game_seed), GREEN: GreedyAgent(game_seed + 100)}
        while len(game.moves) < moves and not game.is_over:
            game.play(agents[game.position.to_move].choose_move(game.position))
        if not game.is_over:
            found.append(game.position)
    return found


def test_pawns_is_my_pawns_minus_the_opponents():
    position = Position.setup(HOLE)
    assert pawns(position, BLUE) == 11 - 9
    assert pawns(position, GREEN) == 9 - 11


@pytest.mark.parametrize("depth", [1, 2, 3])
def test_scores_every_move_exactly_like_plain_minimax(depth):
    for position in positions_from_games(3, moves=8 if depth == 3 else 20):
        me = position.to_move
        thoughts = AlphaBetaAgent(seed=0, depth=depth).think(position)
        expected = {move: minimax(position.play(move), depth - 1, me) for move in position.legal_moves()}
        assert thoughts.scores == expected


def test_at_depth_1_it_scores_moves_like_greedy():
    position = Position.setup(HOLE)
    assert AlphaBetaAgent(depth=1).think(position).scores == GreedyAgent().think(position).scores


def test_at_depth_2_it_sees_the_hole_greedy_leaves():
    thoughts = AlphaBetaAgent(seed=0, depth=2).think(Position.setup(HOLE))

    assert thoughts.scores[Move.parse("c4c6")] == 7 - 13  # Green jumps into c4 and infects 7
    assert thoughts.scores[Move.parse("d4c6")] == 13 - 8
    assert thoughts.move == Move.parse("d4c6")


def test_at_depth_2_it_sees_a_move_that_loses_every_pawn():
    # The one game Greedy lost to Random: Green's g5e3 lets Blue's c4d2 infect both its pawns.
    game = Game()
    for move in "a6 a1b3 a6c4 g7g5 g1e2".split():
        game.play(move)

    thoughts = AlphaBetaAgent(seed=0, depth=2).think(game.position)

    assert thoughts.scores[Move.parse("g5e3")] == -WIN
    assert thoughts.move != Move.parse("g5e3")
    assert thoughts.scores[thoughts.move] > -WIN


def test_a_quick_win_scores_higher_than_a_slow_one():
    # Every move landing next to d4 infects Green's last pawn at once. The other moves win later, or not at all.
    position = Position.setup("""
        B . . . . . .
        . . . . . . .
        . . . . . . .
        . . . G . . .
        . . . . B . .
        . . . . . . .
        . . . . . . .
    """)

    thoughts = AlphaBetaAgent(seed=0, depth=3).think(position)

    for move, score in thoughts.scores.items():
        wins_at_once = position.play(move).result() is not None
        assert (score == WIN + 2) == wins_at_once  # won after 1 move, with 2 moves of depth left
    assert position.play(thoughts.move).result().winner is BLUE


def test_a_pass_gives_the_turn_back_to_the_searcher():
    # After Blue fills b6, Green's a7 has no empty cell within 2 and passes, so Blue moves twice in a row.
    position = Position.setup("""
        G B B . . . .
        B . B . . . .
        B B B . . . .
        . . . . . . .
        . . . . . . .
        . . . . . . .
        . . . . . . .
    """)
    thoughts = AlphaBetaAgent(seed=0, depth=2).think(position)
    me = position.to_move
    assert thoughts.scores == {move: minimax(position.play(move), 1, me) for move in position.legal_moves()}
    assert thoughts.scores[Move.parse("b6")] == WIN + 1  # b6 infects a7: Green has no pawns left


def test_looks_at_fewer_positions_than_plain_minimax():
    def count_minimax(position, depth):
        if depth == 0 or position.ends_game():
            return 0
        return sum(1 + count_minimax(position.play(move), depth - 1) for move in position.legal_moves())

    [position] = positions_from_games(1, moves=20)
    agent = AlphaBetaAgent(depth=3)
    agent.think(position)
    assert agent.positions < count_minimax(position, 3) / 3


def test_its_line_is_a_real_line_of_play():
    for position in positions_from_games(3, moves=20):
        thoughts = AlphaBetaAgent(seed=0, depth=3).think(position)
        assert thoughts.line[0] == thoughts.move
        assert len(thoughts.line) <= 3
        for move in thoughts.line:
            assert position.is_legal(move)
            position = position.play(move)


def test_breaks_ties_at_random():
    # At depth 1 the start looks like Greedy's: all 6 clones are worth +1.
    moves = {str(AlphaBetaAgent(seed, depth=1).choose_move(Position.start())) for seed in range(50)}
    assert moves == {"f1", "f2", "g2", "a6", "b6", "b7"}


def test_stops_when_the_move_is_no_longer_wanted():
    agent = AlphaBetaAgent(seed=0, depth=5)
    agent.stop = threading.Event()
    agent.stop.set()

    thoughts = agent.think(Position.start())

    assert thoughts.move in Position.start().legal_moves()
    assert thoughts.positions < 100  # stopped at once instead of searching about a million positions


def test_plays_only_legal_moves_and_the_same_seed_plays_the_same_game():
    def moves(seed):
        game = Game()
        agents = {BLUE: AlphaBetaAgent(seed, depth=1), GREEN: RandomAgent(seed)}
        while not game.is_over:
            move = agents[game.position.to_move].choose_move(game.position)
            assert game.position.is_legal(move)
            game.play(move)
        return game.moves

    assert moves(1) == moves(1)
    assert moves(1) != moves(2)


def test_looks_3_moves_ahead_unless_told_otherwise():
    assert AlphaBetaAgent().depth == DEPTH == 3
    assert make_agent("AlphaBeta:2").depth == 2
    agent = make_agent("AlphaBeta:pawns:4")
    assert (agent.depth, agent.heuristic, agent.name) == (4, pawns, "AlphaBeta:pawns:4")


@pytest.mark.parametrize("name", ["AlphaBeta:0", "AlphaBeta:2:3", "AlphaBeta:fast", "Greedy:2", "AlphaBeta:pawns:pawns"])
def test_make_agent_refuses_options_it_does_not_know(name):
    with pytest.raises(ValueError):
        make_agent(name)


def test_beats_greedy_clearly():
    tournament = run_tournament("AlphaBeta:2", "Greedy", openings=10, seed=0, workers=1)
    assert mean_and_margin(tournament.points())[0] > 0.8
