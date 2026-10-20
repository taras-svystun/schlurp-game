"""Heuristics and their features."""

import pytest

from schlurp.agents import GreedyAgent, make_agent
from schlurp.agents.alphabeta_agent import WIN
from schlurp.agents.heuristics import (
    FEATURES,
    HEURISTICS,
    LARGEST,
    exposed,
    holes,
    mobility,
    pawns,
    safe_pawns,
    weighted,
)
from schlurp.engine import Game, Player, Position

BLUE, GREEN = Player.BLUE, Player.GREEN

# Blue's ring of 8 pawns around an empty b6, the hole a jump from b6 would leave. Green far away in a corner.
RING = """
    B B B . . . .
    B . B . . . .
    B B B . . . .
    . . . . . . .
    . . . . . . .
    . . . . . G G
    . . . . . G G
"""


def positions_from_games(count=6):
    found = []
    for seed in range(count):
        game = Game()
        agents = {BLUE: GreedyAgent(seed), GREEN: GreedyAgent(seed + 100)}
        while not game.is_over:
            found.append(game.position)
            game.play(agents[game.position.to_move].choose_move(game.position))
    return found


def test_a_hole_is_an_empty_cell_with_4_or_more_of_my_pawns_around_it():
    position = Position.setup(RING)
    assert holes(position, BLUE) == 1  # b6, with all 8 neighbours Blue
    assert holes(position, GREEN) == -1


def test_a_safe_pawn_has_no_empty_neighbour():
    position = Position.setup(RING)
    # Every Blue pawn touches b6 or an empty cell outside the ring. Green's g1 is boxed in by f1, f2 and g2.
    assert safe_pawns(position, GREEN) == 1
    assert safe_pawns(position, BLUE) == -1


def test_exposed_cells_are_next_to_my_pawns_and_reachable_by_the_enemy():
    position = Position.setup("""
        . . . . . . .
        . . . . . . .
        . . . . . . .
        . . . B . G .
        . . . . . . .
        . . . . . . .
        . . . . . . .
    """)
    # Green on f4 reaches columns d to g and rows 2 to 6, so of d4's 8 neighbours it reaches d3, d5, e3, e4, e5.
    # Blue on d4 reaches columns b to f: of f4's neighbours, e3, e4, e5, f3 and f5.
    assert exposed(position, BLUE) == 5 - 5
    far = Position.setup(RING)
    assert exposed(far, BLUE) == 0  # nobody can reach the other's neighbours yet


def test_mobility_counts_the_legal_moves_of_each_player():
    for position in positions_from_games(2)[::7]:
        if position.ends_game():
            continue
        blue = len(Position(position.cells, BLUE).legal_moves())
        green = len(Position(position.cells, GREEN).legal_moves())
        assert mobility(position, BLUE) == blue - green


@pytest.mark.parametrize("feature", [pawns, *FEATURES.values()])
def test_every_feature_is_mine_minus_the_opponents(feature):
    for position in positions_from_games(2)[::5]:
        assert feature(position, BLUE) == -feature(position, GREEN)


@pytest.mark.parametrize("feature", [pawns, *FEATURES.values()])
def test_no_feature_goes_past_its_largest_value(feature):
    for position in positions_from_games():
        assert abs(feature(position, BLUE)) <= LARGEST[feature]


def test_weighted_adds_each_feature_times_its_weight_to_pawns():
    heuristic = weighted({mobility: 0.1, holes: -1})
    for position in positions_from_games(2)[::9]:
        expected = pawns(position, BLUE) + 0.1 * mobility(position, BLUE) - holes(position, BLUE)
        assert heuristic(position, BLUE) == pytest.approx(expected)


def test_weights_are_rounded_so_equal_positions_tie():
    # 0.1 + 0.2 is 0.30000000000000004 in floating point; a heuristic must not see a difference there.
    heuristic = weighted({mobility: 0.1})
    assert heuristic(Position.start(), BLUE) == round(heuristic(Position.start(), BLUE), 6)


@pytest.mark.parametrize("name", HEURISTICS)
def test_no_heuristic_can_look_as_good_as_a_won_game(name):
    heuristic = HEURISTICS[name]
    weights = getattr(heuristic, "weights", {})
    largest = LARGEST[pawns] + sum(abs(weight) * LARGEST[feature] for feature, weight in weights.items())
    assert largest < WIN


def test_weights_that_could_look_like_a_win_are_refused():
    with pytest.raises(ValueError, match="won game"):
        weighted({mobility: 2})


def test_an_agent_name_can_give_feature_weights():
    agent = make_agent("AlphaBeta:2:mobility=0.1:holes=-1")
    assert agent.depth == 2
    assert agent.heuristic.weights == {mobility: 0.1, holes: -1.0}


@pytest.mark.parametrize(
    "name",
    ["AlphaBeta:mobility=x", "AlphaBeta:mobility=inf", "AlphaBeta:pawns:mobility=1", "AlphaBeta:mobility=1:mobility=2",
     "AlphaBeta:speed=1", "Greedy:mobility=1", "AlphaBeta:mobility=5"],
)  # fmt: skip
def test_wrong_feature_weights_are_refused(name):
    with pytest.raises(ValueError):
        make_agent(name)
