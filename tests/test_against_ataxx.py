"""Our rules against the `ataxx` package, our reference (see docs/adr/0001).

Two differences are on purpose: `ataxx` makes a pass an explicit move ("0000") and counts it
towards the fifty-move rule; we pass automatically and count only jumps.
"""

import random

import ataxx
import pytest

from schlurp.engine import CELLS, EMPTY, JUMPS_FOR_DRAW, NEIGHBOURS, SIZE, Move, Player, Position

RESULTS = {"1-0": Player.BLUE, "0-1": Player.GREEN, "1/2-1/2": None}


def perft(position: Position, depth: int) -> int:
    """How many different move sequences of `depth` moves there are from `position`."""
    if depth == 0:
        return 1
    moves = position.legal_moves()
    if depth == 1:
        return len(moves)
    return sum(perft(position.play(move), depth - 1) for move in moves)


def board_fen(position: Position) -> str:
    """The first two parts of a FEN: the board (row 7 first, x for Blue, o for Green) and who is to move."""
    chars = {Player.BLUE.value: "x", Player.GREEN.value: "o"}
    rows = []
    for row in reversed(range(SIZE)):
        text, empty = "", 0
        for value in position.cells[row * SIZE : (row + 1) * SIZE]:
            if value == EMPTY:
                empty += 1
                continue
            text += (str(empty) if empty else "") + chars[value]
            empty = 0
        rows.append(text + (str(empty) if empty else ""))
    return "/".join(rows) + " " + ("x" if position.to_move is Player.BLUE else "o")


@pytest.mark.parametrize("depth, count", [(1, 16), (2, 256), (3, 6460), (4, 155888)])
def test_perft_from_the_start(depth, count):
    assert perft(Position.start(), depth) == count
    assert ataxx.Board().perft(depth) == count


def test_perft_depth_5():
    # The reference's own count, worked out once (it takes it 7 seconds): ataxx.Board().perft(5).
    assert perft(Position.start(), 5) == 4752668


def play_side_by_side(rng: random.Random, jump_chance: float = 0.0) -> dict[str, int]:
    """Play one random game in our engine and in `ataxx` at the same time, and compare them after every move.

    With `jump_chance`, the random player picks a jump that infects nobody that often (when it has one),
    so the game makes long runs of jumps and reaches the fifty-move rule.
    Returns what happened in the game, so the tests can check the rare rules were really tried.
    """
    ours, theirs = Position.start(), ataxx.Board()
    seen = {"moves": 0, "passes": 0, "wipe_outs": 0, "full_boards": 0, "fifty_moves": 0}
    passes_since_clone = 0
    while True:
        their_moves = theirs.legal_moves()
        if their_moves == [ataxx.Move.null()]:
            theirs.makemove(ataxx.Move.null())
            their_moves = theirs.legal_moves()
            seen["passes"] += 1
            passes_since_clone += 1
        assert theirs.get_fen().rsplit(" ", 2)[0] == board_fen(ours)
        assert theirs.halfmove_clock == ours.jumps_in_a_row + passes_since_clone
        moves = ours.legal_moves()
        assert {str(m) for m in their_moves} == {str(m) for m in moves}
        assert theirs.gameover() == ours.ends_game()
        if ours.ends_game():
            result = ours.result()
            assert RESULTS[theirs.result()] is result.winner
            kind = {"no pawns": "wipe_outs", "full board": "full_boards", "fifty-move rule": "fifty_moves"}
            seen[kind[result.ended_by]] += 1
            # `ended_by` reads only the score, so check it against the jump count too.
            assert (result.ended_by == "fifty-move rule") == (ours.jumps_in_a_row >= JUMPS_FOR_DRAW and 0 not in result.score)
            return seen
        enemy = ours.to_move.opponent.value
        quiet_jumps = [
            m for m in moves if m.is_jump and all(ours.cells[n] != enemy for n in NEIGHBOURS[m.target])
        ]
        if quiet_jumps and rng.random() < jump_chance:
            move = rng.choice(quiet_jumps)
        else:
            move = rng.choice(moves)
        ours = ours.play(move)
        theirs.makemove(ataxx.Move.from_san(str(move)))
        seen["moves"] += 1
        if not move.is_jump:
            passes_since_clone = 0


def add_up(games: list[dict[str, int]]) -> dict[str, int]:
    return {key: sum(game[key] for game in games) for key in games[0]}


def test_random_games_match():
    rng = random.Random(1)
    # 150 games, about 29 000 positions. Most of the time goes into the reference, which is slower than our engine.
    seen = add_up([play_side_by_side(rng) for _ in range(150)])
    # Make sure the games went through the rare rules too, not only the usual ones.
    assert seen["passes"] >= 10
    assert seen["wipe_outs"] >= 5
    assert seen["full_boards"] >= 100


def test_jumpy_random_games_match():
    # Players who mostly make jumps that infect nobody make long runs of jumps, so the fifty-move rule comes up.
    rng = random.Random(2)
    seen = add_up([play_side_by_side(rng, jump_chance=0.99) for _ in range(100)])
    assert seen["fifty_moves"] >= 90


def test_moves_add_and_infect_the_right_pawns():
    """Properties that must hold after every move, checked on many random positions."""
    rng = random.Random(3)
    for _ in range(100):
        position = Position.start()
        while not position.ends_game():
            move = rng.choice(position.legal_moves())
            me, enemy = position.to_move, position.to_move.opponent
            near_enemies = sum(position.cells[n] == enemy.value for n in NEIGHBOURS[move.target])
            after = position.play(move)
            grown = 0 if move.is_jump else 1
            assert after.pawns(me) == position.pawns(me) + grown + near_enemies
            assert after.pawns(enemy) == position.pawns(enemy) - near_enemies
            assert after.at(str(Move(move.target))) is me
            if move.is_jump:
                assert after.cells[move.source] == EMPTY
            # Only the target, the source and the target's neighbours may change.
            allowed = {move.target, move.source, *NEIGHBOURS[move.target]}
            changed = {cell for cell in range(CELLS) if after.cells[cell] != position.cells[cell]}
            assert changed <= allowed
            position = after
