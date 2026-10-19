"""Tournament: many games between two AI agents, with no window, to compare them with numbers.

Each random opening is played twice, with the agents swapping players, so neither agent
gets the luckier openings or the better player more often than the other.
Games are spread over several processes, half the CPU cores by default, so the laptop stays cool.
"""

import csv
import math
import os
import random
import statistics
import time
from collections import Counter
from collections.abc import Callable, Iterator
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from schlurp import records
from schlurp.agents import make_agent
from schlurp.engine import Game, Move, Player
from schlurp.records import GameRecord

OPENINGS = 250
OPENING_MOVES = 4
# 95% of the time, the true average is within 1.96 standard errors of the average we measured.
Z_95 = 1.96


def default_workers() -> int:
    """Half the CPU cores: tournaments heat the laptop, and the other half keeps it usable."""
    return max(1, (os.cpu_count() or 2) // 2)


@dataclass(frozen=True)
class GameJob:
    """Everything a worker process needs to play one tournament game."""

    number: int  # 1, 2, 3, ...
    opening: tuple[str, ...]  # moves played at random from the start, like ("b6", "a1c3")
    a_player: Player  # the player agent A is in this game
    blue: str  # agent names for make_agent, like "Random"
    green: str
    blue_seed: int
    green_seed: int


@dataclass(frozen=True)
class GameOutcome:
    job: GameJob
    record: GameRecord  # the whole game, opening included
    thinking: tuple[float, float]  # seconds spent choosing moves, (Blue, Green)
    agent_moves: tuple[int, int]  # moves chosen by each agent, not counting the opening, (Blue, Green)


def play_game(job: GameJob) -> GameOutcome:
    """Play one game. Runs in a worker process, so it builds its own agents from their names."""
    agents = {Player.BLUE: make_agent(job.blue, job.blue_seed), Player.GREEN: make_agent(job.green, job.green_seed)}
    game = Game()
    for move in job.opening:
        game.play(move)
    thinking = {Player.BLUE: 0.0, Player.GREEN: 0.0}
    agent_moves = {Player.BLUE: 0, Player.GREEN: 0}
    while not game.is_over:
        player = game.position.to_move
        started = time.perf_counter()
        move = agents[player].think_in_game(game).move
        thinking[player] += time.perf_counter() - started
        agent_moves[player] += 1
        if not isinstance(move, Move) or not game.position.is_legal(move):
            name = job.blue if player is Player.BLUE else job.green
            raise ValueError(f"Game {job.number}: {name} playing {player.name.title()} chose {move!r}, which is not legal here:\n{game.position}")
        game.play(move)
    record = GameRecord.of(game, job.blue, job.green)
    return GameOutcome(
        job, record, (thinking[Player.BLUE], thinking[Player.GREEN]), (agent_moves[Player.BLUE], agent_moves[Player.GREEN])
    )


def random_openings(count: int, length: int, rng: random.Random) -> list[tuple[str, ...]]:
    """`count` different openings of `length` random legal moves from the start, none of which ends the game."""
    openings: dict[tuple[str, ...], None] = {}  # a dict keeps the order, and skips repeats like a set
    for _ in range(count * 100):
        if len(openings) == count:
            break
        game = Game()
        while len(game.moves) < length and not game.is_over:
            game.play(rng.choice(game.position.legal_moves()))
        if not game.is_over:
            openings[tuple(str(move) for move in game.moves)] = None
    if len(openings) < count:
        raise ValueError(f"Could not find {count} different openings of {length} moves. Use longer openings.")
    return list(openings)


def make_jobs(a: str, b: str, openings: int, opening_moves: int, seed: int) -> list[GameJob]:
    """Two games per opening: A plays Blue in the first and Green in the second. Blue always moves first."""
    rng = random.Random(seed)
    jobs = []
    for opening in random_openings(openings, opening_moves, rng):
        for a_player in Player:
            blue, green = (a, b) if a_player is Player.BLUE else (b, a)
            # Made here, not in the workers, so the same seed always gives the same games.
            seeds = rng.getrandbits(32), rng.getrandbits(32)
            jobs.append(GameJob(len(jobs) + 1, opening, a_player, blue, green, *seeds))
    return jobs


@dataclass(frozen=True)
class Tournament:
    a: str
    b: str
    opening_moves: int
    seed: int
    outcomes: list[GameOutcome]

    def points(self) -> list[float]:
        """Agent A's points in each game: 1 for a win, 1/2 for a draw, 0 for a loss. B gets the rest."""
        points = []
        for outcome in self.outcomes:
            winner = outcome.record.result.winner
            points.append(0.5 if winner is None else 1.0 if winner is outcome.job.a_player else 0.0)
        return points

    def pawn_differences(self) -> list[int]:
        """In each game, the pawns A ended with minus the pawns B ended with."""
        differences = []
        for outcome in self.outcomes:
            blue, green = outcome.record.result.score
            differences.append(blue - green if outcome.job.a_player is Player.BLUE else green - blue)
        return differences

    def seconds_per_move(self, agent: str) -> float:
        """Average time agent "a" or "b" spent choosing one move."""
        thinking = moves = 0
        for outcome in self.outcomes:
            player = outcome.job.a_player if agent == "a" else outcome.job.a_player.opponent
            index = 0 if player is Player.BLUE else 1
            thinking += outcome.thinking[index]
            moves += outcome.agent_moves[index]
        return thinking / moves if moves else 0.0

    def report(self) -> str:
        games = len(self.outcomes)
        points = self.points()
        wins, draws = points.count(1.0), points.count(0.5)
        losses = games - wins - draws
        share, share_margin = mean_and_margin(points)
        difference, difference_margin = mean_and_margin(self.pawn_differences())
        winners = Counter(outcome.record.result.winner for outcome in self.outcomes)
        ended_by = Counter(outcome.record.result.ended_by for outcome in self.outcomes)
        moves = statistics.fmean(len(outcome.record.moves) for outcome in self.outcomes)

        low, high = share - share_margin, share + share_margin
        if low > 0.5:
            verdict = f"A ({self.a}) is stronger: its whole interval is above 50%."
        elif high < 0.5:
            verdict = f"B ({self.b}) is stronger: A's whole interval is below 50%."
        else:
            verdict = "The interval includes 50%, so these games cannot tell the two agents apart."

        return "\n".join(
            [
                f"A: {self.a}    B: {self.b}",
                f"{games} games: {games // 2} random openings of {self.opening_moves} moves, "
                "each played twice with the agents swapping players.",
                "",
                f"A wins {wins} ({percent(wins / games)}), draws {draws} ({percent(draws / games)}), "
                f"loses {losses} ({percent(losses / games)}).",
                f"A's points: {percent(share)} ± {percent(share_margin)}  "
                "(a win is 1 point, a draw 1/2; 95% confidence interval)",
                f"Pawns at the end, A minus B: {difference:+.1f} ± {difference_margin:.1f} on average.",
                f"Time per move: A {duration(self.seconds_per_move('a'))}, B {duration(self.seconds_per_move('b'))}.",
                f"By player: Blue won {winners[Player.BLUE]}, Green won {winners[Player.GREEN]}, "
                f"{winners[None]} draws.",
                f"Games ended by: full board {ended_by['full board']}, no pawns {ended_by['no pawns']}, "
                f"fifty-move rule {ended_by['fifty-move rule']}. {moves:.0f} moves per game on average.",
                "",
                verdict,
                f"Seed {self.seed}: add --seed {self.seed} to play exactly the same games again.",
            ]
        )

    def save(self) -> Path:
        """Write one CSV row per game in records/tournaments, keeping only the newest KEEP_TOURNAMENTS."""
        folder = records.RECORDS_DIR / "tournaments"
        path = records.new_record_file(folder, f"{self.a}-vs-{self.b}.csv", records.KEEP_TOURNAMENTS)
        with path.open("w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(
                ["game", "blue", "green", "a_plays", "winner", "blue_pawns", "green_pawns", "ended_by",
                 "moves", "blue_ms_per_move", "green_ms_per_move", "opening", "record"]
            )  # fmt: skip
            for outcome in self.outcomes:
                job, record = outcome.job, outcome.record
                ms_per_move = [
                    f"{seconds / moves * 1000:.3f}" if moves else ""
                    for seconds, moves in zip(outcome.thinking, outcome.agent_moves)
                ]
                writer.writerow(
                    [job.number, job.blue, job.green, job.a_player.name.title(),
                     record.result.winner.name.title() if record.result.winner else "Draw", *record.result.score,
                     record.result.ended_by, len(record.moves), *ms_per_move,
                     " ".join(job.opening), " ".join(record.moves)]
                )  # fmt: skip
        return path


def run_tournament(
    a: str,
    b: str,
    openings: int = OPENINGS,
    opening_moves: int = OPENING_MOVES,
    seed: int | None = None,
    workers: int | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> Tournament:
    """Play agent A against agent B (names for make_agent, like "Random"): two games per random opening.

    With no `seed`, one is chosen at random and kept in the report, so any tournament can be repeated.
    `workers` is the number of processes, half the CPU cores by default. With 1, everything runs here.
    `on_progress(done, total)` is called after each game.
    """
    if seed is None:
        seed = random.randrange(1_000_000)
    jobs = make_jobs(a, b, openings, opening_moves, seed)
    outcomes = []
    for outcome in play_all(jobs, workers or default_workers()):
        outcomes.append(outcome)
        if on_progress:
            on_progress(len(outcomes), len(jobs))
    return Tournament(a, b, opening_moves, seed, outcomes)


def play_all(jobs: list[GameJob], workers: int) -> Iterator[GameOutcome]:
    """Play the games in `workers` processes, and give back their outcomes in the same order as the jobs."""
    if workers == 1:
        yield from map(play_game, jobs)
        return
    with ProcessPoolExecutor(workers) as executor:
        # Send the games in small batches: one at a time would spend more time talking than playing.
        chunk = max(1, len(jobs) // (workers * 10))
        yield from executor.map(play_game, jobs, chunksize=chunk)


def mean_and_margin(values: list[float]) -> tuple[float, float]:
    """The average, and how far the true average may be from it (95% confidence).

    The margin is 1.96 standard errors: the spread of the values divided by the square root
    of how many there are. Four times more games make the margin two times smaller.
    """
    mean = statistics.fmean(values)
    if len(values) < 2:
        return mean, math.inf
    return mean, Z_95 * statistics.stdev(values) / math.sqrt(len(values))


def percent(share: float) -> str:
    return f"{share * 100:.1f}%"


def duration(seconds: float) -> str:
    if seconds < 0.001:
        return f"{seconds * 1_000_000:.0f} µs"
    if seconds < 1:
        return f"{seconds * 1000:.1f} ms"
    return f"{seconds:.2f} s"
