"""Game records: saving, loading and replaying games."""

import json

import pytest

from schlurp import records
from schlurp.agents import RandomAgent
from schlurp.engine import Game, Player, Position, Result
from schlurp.records import GameRecord, load_game, new_record_file, save_game


def random_game(first=Player.BLUE, seed=0) -> Game:
    game = Game(first=first)
    agent = RandomAgent(seed)
    while not game.is_over:
        game.play(agent.choose_move(game.position))
    return game


def test_a_record_keeps_who_moved_first_the_moves_and_the_result():
    game = random_game(first=Player.GREEN)

    record = GameRecord.of(game, "Person", "Random")

    assert record.first is Player.GREEN
    assert record.moves == tuple(str(move) for move in game.moves)
    assert record.result == game.result


def test_replaying_a_record_gives_the_same_game():
    for first in Player:
        for seed in range(5):
            game = random_game(first, seed)

            replayed = GameRecord.of(game, "Random", "Random").replay()

            assert replayed.positions == game.positions  # passes included: the engine makes them again


def test_a_record_whose_moves_do_not_give_its_result_cannot_be_replayed():
    record = GameRecord.of(random_game(), "Random", "Random")
    wrong = GameRecord(record.blue, record.green, record.first, record.moves, Result(None, (1, 1)))

    with pytest.raises(ValueError, match="the record says"):
        wrong.replay()


def test_only_finished_games_from_the_start_position_can_be_recorded():
    unfinished = Game()
    unfinished.play("b6")
    set_up = Game(start=Position.setup("\n".join(["BBBBBBB"] * 3 + ["GGGGGGG"] * 3 + ["GGGGGG."])))
    set_up.play("g1")

    with pytest.raises(ValueError, match="finished"):
        GameRecord.of(unfinished, "Person", "Person")
    with pytest.raises(ValueError, match="start position"):
        GameRecord.of(set_up, "Person", "Person")


def test_a_saved_game_loads_back_the_same(records_in_a_temporary_folder):
    record = GameRecord.of(random_game(), "Person", "Random")

    path = save_game(record)

    assert path.parent == records_in_a_temporary_folder / "games"
    assert load_game(path) == record
    data = json.loads(path.read_text())
    assert (data["blue"], data["green"], data["first"]) == ("Person", "Random", "Blue")
    assert data["moves"] == " ".join(record.moves)  # easy to read in the file
    assert data["ended_by"] == record.result.ended_by


def test_only_the_newest_records_are_kept(tmp_path):
    folder = tmp_path / "some records"
    for i in range(5):
        new_record_file(folder, f"{i}.txt", keep=3).write_text(str(i))

    assert [path.read_text() for path in sorted(folder.iterdir())] == ["2", "3", "4"]


def test_a_colon_in_an_agent_name_is_not_put_in_a_file_name(tmp_path):
    assert ":" not in new_record_file(tmp_path, "AlphaBeta:4-vs-Random.json", keep=10).name


def test_save_game_keeps_the_last_100_games(monkeypatch, records_in_a_temporary_folder):
    monkeypatch.setattr(records, "KEEP_GAMES", 3)
    record = GameRecord.of(random_game(), "Random", "Random")

    for _ in range(5):
        save_game(record)

    assert len(list((records_in_a_temporary_folder / "games").iterdir())) == 3
