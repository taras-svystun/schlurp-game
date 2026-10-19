"""The rules of Schlurp. No UI and no AI here, only the game itself.

The board is stored as a tuple of 49 numbers, one per cell: 0 for empty, 1 for Blue, 2 for Green.
A cell's index is row * 7 + column, where row 0 is the bottom row ("1") and column 0 the left
column ("a"). So a1 is 0, g1 is 6, a7 is 42 and g7 is 48.
"""

from dataclasses import dataclass
from enum import Enum
from typing import NamedTuple

SIZE = 7
CELLS = SIZE * SIZE
EMPTY = 0
# Fifty-move rule: this many jumps in a row (by both players together) end the game in a draw.
JUMPS_FOR_DRAW = 100
COLUMNS = "abcdefg"


class Player(Enum):
    BLUE = 1
    GREEN = 2

    @property
    def opponent(self) -> "Player":
        return Player.GREEN if self is Player.BLUE else Player.BLUE

    @property
    def letter(self) -> str:
        """How the player's pawns are drawn in a text picture of the board."""
        return self.name[0]


def cell_name(cell: int) -> str:
    """0 is "a1", 48 is "g7"."""
    row, column = divmod(cell, SIZE)
    return f"{COLUMNS[column]}{row + 1}"


def cell_index(name: str) -> int:
    """The opposite of `cell_name`: "a1" is 0, "g7" is 48."""
    if len(name) != 2 or name[0] not in COLUMNS or name[1] not in "1234567":
        raise ValueError(f"{name!r} is not a cell: use a column a-g and a row 1-7, like 'c3'")
    return (int(name[1]) - 1) * SIZE + COLUMNS.index(name[0])


def _cells_at_distance(cell: int, distance: int) -> tuple[int, ...]:
    """Cells exactly `distance` steps away, where a step may be straight or diagonal."""
    row, column = divmod(cell, SIZE)
    return tuple(
        r * SIZE + c
        for r in range(max(0, row - distance), min(SIZE, row + distance + 1))
        for c in range(max(0, column - distance), min(SIZE, column + distance + 1))
        if max(abs(r - row), abs(c - column)) == distance
    )


# Worked out once, so the rules never need to check the edges of the board.
NEIGHBOURS = tuple(_cells_at_distance(cell, 1) for cell in range(CELLS))  # up to 8 per cell
JUMP_TARGETS = tuple(_cells_at_distance(cell, 2) for cell in range(CELLS))  # up to 16 per cell
WITHIN_TWO = tuple(NEIGHBOURS[cell] + JUMP_TARGETS[cell] for cell in range(CELLS))


class Move(NamedTuple):
    """A clone or a jump.

    A clone has no source: clones onto the same cell from any of your pawns give the same
    position, so they are one move. Written as the target cell ("c3"), a jump as both cells ("a1c3").
    """

    target: int  # the cell the new or moved pawn lands on
    source: int | None = None  # the cell a jump starts from; None for a clone

    @property
    def is_jump(self) -> bool:
        return self.source is not None

    def __str__(self) -> str:
        if self.source is None:
            return cell_name(self.target)
        return cell_name(self.source) + cell_name(self.target)

    @classmethod
    def parse(cls, text: str) -> "Move":
        """The opposite of `str(move)`: "c3" is a clone onto c3, "a1c3" a jump from a1 to c3."""
        if len(text) == 2:
            return cls(cell_index(text))
        if len(text) == 4:
            return cls(cell_index(text[2:]), cell_index(text[:2]))
        raise ValueError(f"{text!r} is not a move: write a clone like 'c3' or a jump like 'a1c3'")


@dataclass(frozen=True)
class Result:
    winner: Player | None  # None means a draw
    score: tuple[int, int]  # pawns at the end, (Blue, Green)

    @property
    def ended_by(self) -> str:
        """Why the game ended: "no pawns", "full board" or "fifty-move rule".

        The score alone tells it: the fifty-move rule ends a game after a jump, which always leaves
        an empty cell, so the board is never full then, and both players still have pawns.
        """
        if 0 in self.score:
            return "no pawns"
        if sum(self.score) == CELLS:
            return "full board"
        return "fifty-move rule"


@dataclass(frozen=True, slots=True)
class Position:
    """The board, whose turn it is, and how many jumps in a row were just made. Never changes after it is made.

    The player to move always has a legal move, unless the game is over: when a player cannot move,
    `play` already gave the turn back to the other player (a pass).
    """

    cells: tuple[int, ...]
    to_move: Player
    jumps_in_a_row: int = 0  # for the fifty-move rule; a clone sets it back to 0

    @classmethod
    def start(cls, first: Player = Player.BLUE) -> "Position":
        cells = [EMPTY] * CELLS
        cells[cell_index("a7")] = cells[cell_index("g1")] = Player.BLUE.value
        cells[cell_index("a1")] = cells[cell_index("g7")] = Player.GREEN.value
        return cls(tuple(cells), first)

    @classmethod
    def setup(cls, picture: str, to_move: Player = Player.BLUE, jumps_in_a_row: int = 0) -> "Position":
        """Make any position from a picture of the board: 7 lines of 7 characters, the top row (row 7) first.

        B is a Blue pawn, G a Green pawn and . an empty cell. Spaces are ignored. If the player
        to move cannot move, the turn passes to the other player, as it would in a game.
        """
        rows = [line.replace(" ", "") for line in picture.strip().splitlines()]
        if len(rows) != SIZE or any(len(row) != SIZE for row in rows):
            raise ValueError(f"A picture of the board needs {SIZE} lines of {SIZE} cells")
        values = {".": EMPTY, "B": Player.BLUE.value, "G": Player.GREEN.value}
        cells = tuple(values[char] for row in reversed(rows) for char in row)
        return cls(cells, to_move, jumps_in_a_row)._with_pass()

    def __str__(self) -> str:
        """The board as a picture, like the one `setup` takes."""
        chars = {EMPTY: ".", Player.BLUE.value: "B", Player.GREEN.value: "G"}
        rows = [" ".join(chars[v] for v in self.cells[row * SIZE : (row + 1) * SIZE]) for row in range(SIZE)]
        return "\n".join(reversed(rows)) + f"\n{self.to_move.name.title()} to move"

    def at(self, name: str) -> Player | None:
        """The owner of the pawn on a cell named like "c3", or None if it is empty."""
        value = self.cells[cell_index(name)]
        return None if value == EMPTY else Player(value)

    def pawns(self, player: Player) -> int:
        return self.cells.count(player.value)

    def ends_game(self) -> bool:
        """True if the game is over: the board is full, a player has no pawns, or the fifty-move rule.

        The rules also end the game when neither player can move, but with no blocked cells that only
        happens in those cases: if no pawn is within 2 cells of an empty cell, its neighbours are all
        empty too, and so are theirs, and so on until the whole board is empty.
        """
        cells = self.cells
        return (
            EMPTY not in cells
            or Player.BLUE.value not in cells
            or Player.GREEN.value not in cells
            or self.jumps_in_a_row >= JUMPS_FOR_DRAW
        )

    def result(self) -> Result | None:
        """Who won, if the game is over here. None while it goes on."""
        if not self.ends_game():
            return None
        blue, green = self.pawns(Player.BLUE), self.pawns(Player.GREEN)
        score = (blue, green)
        if blue == 0 or green == 0 or EMPTY not in self.cells:
            # A player without pawns loses even on the 100th jump, like in standard Ataxx.
            winner = Player.BLUE if blue > green else Player.GREEN if green > blue else None
            return Result(winner, score)
        return Result(None, score)  # the fifty-move rule

    def legal_moves(self) -> list[Move]:
        """Every clone (one per target cell) and every jump of the player to move. Empty when the game is over."""
        if self.ends_game():
            return []
        cells, me = self.cells, self.to_move.value
        moves = []
        for cell in range(CELLS):
            if cells[cell] == EMPTY:
                for neighbour in NEIGHBOURS[cell]:
                    if cells[neighbour] == me:
                        moves.append(Move(cell))
                        break
            elif cells[cell] == me:
                for target in JUMP_TARGETS[cell]:
                    if cells[target] == EMPTY:
                        moves.append(Move(target, cell))
        return moves

    def is_legal(self, move: Move) -> bool:
        """The same as `move in self.legal_moves()`, without making the whole list."""
        cells, me = self.cells, self.to_move.value
        target, source = move
        if self.ends_game() or not 0 <= target < CELLS or cells[target] != EMPTY:
            return False
        if source is None:
            return any(cells[neighbour] == me for neighbour in NEIGHBOURS[target])
        return 0 <= source < CELLS and cells[source] == me and target in JUMP_TARGETS[source]

    def play(self, move: Move) -> "Position":
        """Return the position after the player to move makes `move`, with the infections and a pass if needed."""
        if not self.is_legal(move):
            raise ValueError(f"{self.to_move.name.title()} cannot play {move}\n{self}")
        me, enemy = self.to_move.value, self.to_move.opponent.value
        cells = list(self.cells)
        cells[move.target] = me
        if move.source is not None:
            cells[move.source] = EMPTY
        for neighbour in NEIGHBOURS[move.target]:
            if cells[neighbour] == enemy:
                cells[neighbour] = me  # infected
        jumps = self.jumps_in_a_row + 1 if move.source is not None else 0
        return Position(tuple(cells), self.to_move.opponent, jumps)._with_pass()

    def can_move(self, player: Player) -> bool:
        """True if `player` has a pawn with an empty cell at most 2 cells away."""
        cells, me = self.cells, player.value
        for cell in range(CELLS):
            if cells[cell] == me:
                for near in WITHIN_TWO[cell]:
                    if cells[near] == EMPTY:
                        return True
        return False

    def _with_pass(self) -> "Position":
        """If the player to move cannot move but the game goes on, give the turn to the other player.

        The other player can then always move: there is an empty cell and pawns on the board, so
        someone has a pawn near an empty cell (see `ends_game`).
        """
        if self.ends_game() or self.can_move(self.to_move):
            return self
        return Position(self.cells, self.to_move.opponent, self.jumps_in_a_row)


class Game:
    """A whole game: every position from the start, the moves, and how it ended."""

    def __init__(self, first: Player = Player.BLUE, start: Position | None = None):
        self._positions = [start or Position.start(first)]
        self.moves: list[Move] = []

    @property
    def position(self) -> Position:
        return self._positions[-1]

    @property
    def positions(self) -> tuple[Position, ...]:
        """Every position so far, from the start to now. `positions[k]` is the position after k moves.

        `positions[k].to_move` made move k, so passes need no entry of their own.
        """
        return tuple(self._positions)

    @property
    def is_over(self) -> bool:
        return self.position.ends_game()

    @property
    def result(self) -> Result | None:
        return self.position.result()

    def play(self, move: Move | str) -> None:
        """Make a move, given as a Move or written like "c3" or "a1c3"."""
        if isinstance(move, str):
            move = Move.parse(move)
        if self.is_over:
            raise ValueError("The game is over")
        self._positions.append(self.position.play(move))
        self.moves.append(move)

    def copy(self) -> "Game":
        """The same game as a new object: moves and undos in one do not change the other."""
        game = Game(start=self._positions[0])
        game._positions, game.moves = list(self._positions), list(self.moves)
        return game

    def undo(self) -> None:
        """Take back the last move."""
        if not self.moves:
            raise ValueError("There is no move to undo")
        self._positions.pop()
        self.moves.pop()
