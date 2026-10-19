"""The Random agent."""

from collections import Counter

from schlurp.agents import RandomAgent
from schlurp.engine import Game, Move, Position


def play_whole_game(blue, green) -> list[Move]:
    game = Game()
    agents = {"BLUE": blue, "GREEN": green}
    while not game.is_over:
        move = agents[game.position.to_move.name].choose_move(game.position)
        assert game.position.is_legal(move)
        game.play(move)
    return game.moves


def test_plays_only_legal_moves_until_the_game_ends():
    for seed in range(10):
        play_whole_game(RandomAgent(seed), RandomAgent(seed + 100))


def test_plays_the_only_legal_move():
    # Blue's only pawn sits in a corner with every neighbour taken by Green, and only a5 is free to jump to.
    position = Position.setup("""
        B G G G G G G
        G G G G G G G
        . G G G G G G
        G G G G G G G
        G G G G G G G
        G G G G G G G
        G G G G G G G
    """)
    assert [str(m) for m in position.legal_moves()] == ["a7a5"]
    for seed in range(10):
        assert RandomAgent(seed).choose_move(position) == Move.parse("a7a5")


def test_chooses_every_legal_move_about_equally_often():
    agent = RandomAgent(seed=0)
    counts = Counter(str(agent.choose_move(Position.start())) for _ in range(1600))
    assert len(counts) == 16
    # About 100 each. Anything outside 50-150 is almost impossible for a fair choice.
    assert all(50 <= count <= 150 for count in counts.values()), counts


def test_the_same_seed_plays_the_same_game():
    first = play_whole_game(RandomAgent(seed=1), RandomAgent(seed=2))
    again = play_whole_game(RandomAgent(seed=1), RandomAgent(seed=2))
    other = play_whole_game(RandomAgent(seed=3), RandomAgent(seed=4))
    assert first == again
    assert first != other
