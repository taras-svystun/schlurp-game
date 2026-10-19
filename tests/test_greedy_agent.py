"""The Greedy agent."""

from collections import Counter

from schlurp.agents import GreedyAgent, RandomAgent
from schlurp.engine import Game, Move, Player, Position

COLONY = """
    . . . . . . .
    . . . . . . .
    . . G G . . .
    . . G . B . .
    . . G G . . .
    . . . . . . .
    B . . . . . G
"""


def test_takes_the_move_with_the_best_pawn_difference():
    # The clone d4 lands in the middle of Green's colony and infects all 5 neighbours: Blue 8, Green 1.
    for seed in range(10):
        assert GreedyAgent(seed).choose_move(Position.setup(COLONY)) == Move.parse("d4")


def test_scores_every_legal_move_by_the_pawn_difference_after_it():
    position = Position.setup(COLONY)

    thoughts = GreedyAgent(seed=0).think(position)

    assert set(thoughts.scores) == set(position.legal_moves())
    for move, score in thoughts.scores.items():
        after = position.play(move)
        assert score == after.pawns(Player.BLUE) - after.pawns(Player.GREEN)
    assert thoughts.scores[Move.parse("d4")] == 8 - 1
    assert thoughts.line == (thoughts.move,)
    assert thoughts.positions == len(position.legal_moves())
    assert thoughts.depth == 1


def test_chooses_at_random_between_equally_good_moves():
    # At the start every clone gives 3 pawns against 2, and every jump 2 against 2.
    counts = Counter(str(GreedyAgent(seed).choose_move(Position.start())) for seed in range(600))

    assert set(counts) == {"f1", "f2", "g2", "a6", "b6", "b7"}  # the 6 clones, never a jump
    assert all(60 <= count <= 140 for count in counts.values()), counts  # about 100 each


def test_jumps_only_when_the_jump_infects_more():
    # A clone adds one pawn more than a jump, so with equal infections Greedy clones (see the start position above).
    # Here the best clone, d4, infects only d5: Blue 4, Green 5. A jump to c2 infects b1, b2 and b3: Blue 5, Green 3.
    position = Position.setup("""
        . . . . . . .
        . . . . . . .
        . . . G . . .
        . . . . B . .
        G G . . . . .
        G G . . . . .
        B G . . . . .
    """)

    thoughts = GreedyAgent(seed=0).think(position)

    best_clone = max(score for move, score in thoughts.scores.items() if not move.is_jump)
    assert best_clone == thoughts.scores[Move.parse("d4")] == -1
    assert thoughts.move.is_jump and str(thoughts.move)[2:] == "c2"
    assert thoughts.scores[thoughts.move] == 2


def test_plays_only_legal_moves_until_the_game_ends():
    for seed in range(10):
        game = Game()
        agents = {Player.BLUE: GreedyAgent(seed), Player.GREEN: RandomAgent(seed)}
        while not game.is_over:
            move = agents[game.position.to_move].choose_move(game.position)
            assert game.position.is_legal(move)
            game.play(move)


def test_the_same_seed_plays_the_same_game():
    def moves(seed):
        game = Game()
        agents = {Player.BLUE: GreedyAgent(seed), Player.GREEN: GreedyAgent(seed + 1)}
        while not game.is_over:
            game.play(agents[game.position.to_move].choose_move(game.position))
        return game.moves

    assert moves(1) == moves(1)
    assert moves(1) != moves(3)
