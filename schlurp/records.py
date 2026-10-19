"""Game records: saved games, and where they are kept. No Pygame here.

Moves are written in standard Ataxx notation, like "b6" (a clone) and "a1c3" (a jump).
They do not say who made them, so a record also keeps who moved first: replaying the moves
from the start then tells whose turn each one was, passes included.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from schlurp.engine import Game, Player, Position, Result

# The `records` folder next to the `schlurp` package, i.e. in the project folder. Git ignores it.
RECORDS_DIR = Path(__file__).resolve().parent.parent / "records"
KEEP_GAMES = 100
KEEP_TOURNAMENTS = 10


@dataclass(frozen=True)
class GameRecord:
    """A finished game: who played Blue and Green, who moved first, the moves, and the result."""

    blue: str  # the agent's name, like "Random", or "Person"
    green: str
    first: Player
    moves: tuple[str, ...]  # like ("b6", "a1c3")
    result: Result

    @classmethod
    def of(cls, game: Game, blue: str, green: str) -> "GameRecord":
        if game.result is None:
            raise ValueError("Only a finished game can be recorded")
        first = game.positions[0].to_move
        if game.positions[0] != Position.start(first):
            raise ValueError("Only a game from the start position can be recorded: its moves alone must tell the game")
        return cls(blue, green, first, tuple(str(move) for move in game.moves), game.result)

    def replay(self) -> Game:
        """Play the moves again in a new game, so you can look at any position of it."""
        game = Game(first=self.first)
        for move in self.moves:
            game.play(move)
        if game.result != self.result:
            raise ValueError(f"The moves end with {game.result}, but the record says {self.result}")
        return game

    def to_dict(self) -> dict:
        return {
            "blue": self.blue,
            "green": self.green,
            "first": self.first.name.title(),
            "moves": " ".join(self.moves),
            "winner": self.result.winner.name.title() if self.result.winner else "Draw",
            "score": list(self.result.score),
            "ended_by": self.result.ended_by,  # only to read in the file: the score already tells it
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GameRecord":
        winner = None if data["winner"] == "Draw" else Player[data["winner"].upper()]
        blue, green = data["score"]
        result = Result(winner, (blue, green))
        return cls(data["blue"], data["green"], Player[data["first"].upper()], tuple(data["moves"].split()), result)


def save_game(record: GameRecord) -> Path:
    """Save a Play or Watch game in records/games, keeping only the newest KEEP_GAMES."""
    path = new_record_file(RECORDS_DIR / "games", f"{record.blue}-vs-{record.green}.json", KEEP_GAMES)
    data = {"played_at": datetime.now().isoformat(timespec="seconds"), **record.to_dict()}
    path.write_text(json.dumps(data, indent=2) + "\n")
    return path


def load_game(path: Path) -> GameRecord:
    return GameRecord.from_dict(json.loads(Path(path).read_text()))


def new_record_file(folder: Path, name: str, keep: int) -> Path:
    """A path for a new file in `folder`, named by the time now so the files sort from old to new.

    Deletes the oldest files so that, with the new one, at most `keep` are left.
    Agent names may hold a colon (like "AlphaBeta:4"), which is not allowed in file names everywhere,
    so it becomes a dash.
    """
    folder.mkdir(parents=True, exist_ok=True)
    old = sorted(folder.iterdir())
    for path in old[: max(0, len(old) - keep + 1)]:
        path.unlink()
    return folder / f"{datetime.now():%Y-%m-%d_%H-%M-%S-%f}_{name.replace(':', '-')}"
