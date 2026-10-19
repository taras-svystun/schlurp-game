"""Tournament: random openings, fair player swapping, the numbers in the report, and the CSV."""

import csv
import random
import subprocess
import sys
import time
from pathlib import Path

import pytest

from schlurp import agents, records
from schlurp.agents import Agent
from schlurp.engine import Game, Move, Player
from schlurp.records import GameRecord
from schlurp.tournament import default_workers, make_jobs, mean_and_margin, random_openings, run_tournament

SCHLURP = Path(sys.executable).parent / "schlurp"


class PawnsAgent(Agent):
    """A test agent that plays the move giving it the most pawns. It should beat Random clearly."""

    name = "Pawns"

    def choose_move(self, position):
        me = position.to_move
        return max(position.legal_moves(), key=lambda move: position.play(move).pawns(me))


class SlowAgent(Agent):
    """A test agent that takes 2 ms per move, to check the time per move."""

    name = "Slow"

    def choose_move(self, position):
        time.sleep(0.002)
        return position.legal_moves()[0]


class CheatingAgent(Agent):
    """A test agent that clones onto a cell nowhere near its pawns."""

    name = "Cheat"

    def choose_move(self, position):
        return Move.parse("d4")


@pytest.fixture(autouse=True)
def test_agents(monkeypatch):
    # Only for games in this process (workers=1): other processes do not see these agents.
    monkeypatch.setitem(agents.AGENTS, "Pawns", PawnsAgent)
    monkeypatch.setitem(agents.AGENTS, "Slow", SlowAgent)
    monkeypatch.setitem(agents.AGENTS, "Cheat", CheatingAgent)


def test_openings_are_different_and_none_ends_the_game():
    openings = random_openings(250, 4, random.Random(0))

    assert len(set(openings)) == 250
    for opening in openings:
        game = Game()
        for move in opening:
            game.play(move)
        assert len(opening) == 4 and not game.is_over


def test_each_opening_is_played_twice_with_the_agents_swapping_players():
    jobs = make_jobs("Pawns", "Random", openings=10, opening_moves=4, seed=0)

    assert len(jobs) == 20
    assert [job.number for job in jobs] == list(range(1, 21))
    for first, second in zip(jobs[::2], jobs[1::2]):
        assert first.opening == second.opening
        assert (first.a_player, first.blue, first.green) == (Player.BLUE, "Pawns", "Random")
        assert (second.a_player, second.blue, second.green) == (Player.GREEN, "Random", "Pawns")


def test_random_against_random_is_about_even():
    tournament = run_tournament("Random", "Random", seed=0, workers=1)

    share, margin = mean_and_margin(tournament.points())
    assert len(tournament.outcomes) == 500
    assert share - margin < 0.5 < share + margin
    assert "cannot tell the two agents apart" in tournament.report()


def test_a_stronger_agent_wins_whichever_player_it_is():
    as_a = run_tournament("Pawns", "Random", openings=20, seed=0, workers=1)
    as_b = run_tournament("Random", "Pawns", openings=20, seed=0, workers=1)

    assert mean_and_margin(as_a.points())[0] > 0.8
    assert mean_and_margin(as_b.points())[0] < 0.2
    assert sum(as_a.pawn_differences()) > 0
    assert "A (Pawns) is stronger" in as_a.report()
    assert "B (Pawns) is stronger" in as_b.report()


def test_the_same_seed_plays_the_same_games():
    def moves(seed):
        return [outcome.record.moves for outcome in run_tournament("Random", "Random", 20, seed=seed, workers=1).outcomes]

    assert moves(1) == moves(1)
    assert moves(1) != moves(2)


def test_with_no_seed_the_report_says_how_to_play_the_same_games_again():
    tournament = run_tournament("Random", "Random", openings=2, workers=1)

    again = run_tournament("Random", "Random", openings=2, seed=tournament.seed, workers=1)

    assert f"--seed {tournament.seed}" in tournament.report()
    assert [o.record for o in again.outcomes] == [o.record for o in tournament.outcomes]


def test_many_processes_give_the_same_games_as_one():
    one = run_tournament("Random", "Random", openings=20, seed=5, workers=1)
    two = run_tournament("Random", "Random", openings=20, seed=5, workers=2)

    assert [o.record for o in one.outcomes] == [o.record for o in two.outcomes]


def test_by_default_half_the_cpu_cores_are_used(monkeypatch):
    monkeypatch.setattr("os.cpu_count", lambda: 8)
    assert default_workers() == 4
    monkeypatch.setattr("os.cpu_count", lambda: 1)
    assert default_workers() == 1


def test_time_per_move_is_measured_for_each_agent():
    tournament = run_tournament("Slow", "Random", openings=1, seed=0, workers=1)

    assert tournament.seconds_per_move("a") >= 0.002
    assert tournament.seconds_per_move("b") < 0.001


def test_an_illegal_move_stops_the_tournament_and_names_the_agent():
    with pytest.raises(ValueError, match="Game 1: Cheat playing Blue chose .* not legal"):
        run_tournament("Cheat", "Random", openings=1, opening_moves=0, seed=0, workers=1)


def test_progress_is_reported_after_each_game():
    calls = []

    run_tournament("Random", "Random", openings=3, seed=0, workers=1, on_progress=lambda *call: calls.append(call))

    assert calls == [(1, 6), (2, 6), (3, 6), (4, 6), (5, 6), (6, 6)]


def test_a_saved_tournament_has_one_csv_row_per_game(records_in_a_temporary_folder):
    tournament = run_tournament("Pawns", "Random", openings=5, seed=0, workers=1)

    path = tournament.save()

    assert path.parent == records_in_a_temporary_folder / "tournaments"
    rows = list(csv.DictReader(path.open()))
    assert len(rows) == 10
    for row, outcome in zip(rows, tournament.outcomes):
        record = GameRecord(row["blue"], row["green"], Player.BLUE, tuple(row["record"].split()), outcome.record.result)
        game = record.replay()  # the moves in the CSV are the whole game, and give its result
        assert row["winner"] == (game.result.winner.name.title() if game.result.winner else "Draw")
        assert row["ended_by"] == game.result.ended_by
        assert row["record"].startswith(row["opening"])


def test_only_the_last_10_tournaments_are_kept(monkeypatch, records_in_a_temporary_folder):
    monkeypatch.setattr(records, "KEEP_TOURNAMENTS", 2)
    tournament = run_tournament("Random", "Random", openings=1, seed=0, workers=1)

    for _ in range(4):
        tournament.save()

    assert len(list((records_in_a_temporary_folder / "tournaments").iterdir())) == 2


def test_the_tournament_command_prints_the_report():
    result = subprocess.run(
        [SCHLURP, "tournament", "Random", "Random", "--openings", "5", "--seed", "1", "--workers", "1"],
        capture_output=True, text=True, check=True,
    )  # fmt: skip

    assert "10 games: 5 random openings of 4 moves" in result.stdout
    assert "A's points:" in result.stdout
    assert "Seed 1" in result.stdout
    assert "Played 10 of 10 games" in result.stderr


def test_the_tournament_command_refuses_an_unknown_agent_before_playing():
    result = subprocess.run([SCHLURP, "tournament", "Random:3", "Random"], capture_output=True, text=True)

    assert result.returncode != 0
    assert "Random has nothing to set" in result.stderr


def test_the_tournament_never_loads_pygame():
    code = "import sys, schlurp.tournament, schlurp.records; sys.exit('pygame' in sys.modules)"
    assert subprocess.run([sys.executable, "-c", code]).returncode == 0
