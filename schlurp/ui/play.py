"""Play: two people share one computer and take turns clicking the board."""

import time

import pygame

from schlurp.engine import EMPTY, JUMP_TARGETS, NEIGHBOURS, Game, Move, Player, Position
from schlurp.ui.board_view import (
    BACKGROUND,
    HEIGHT,
    LOOKS,
    TEXT,
    TEXT_SOFT,
    BoardView,
    MoveAnimation,
    cell_at,
)
from schlurp.ui.widgets import Button

HELP = "Click a pawn, then a cell. Or click an empty cell next to your pawns to clone there."
KEYS = "N: new game    Esc: quit"
PANEL_X = 720  # the side panel, right of the lens
MOVES_SHOWN = 10


def movable_pawns(position: Position) -> set[int]:
    """The cells of the pawns of the player to move that have at least one move."""
    me, pawns = position.to_move.value, set()
    for move in position.legal_moves():
        if move.source is not None:
            pawns.add(move.source)
        else:
            pawns.update(n for n in NEIGHBOURS[move.target] if position.cells[n] == me)
    return pawns


def reachable(position: Position, pawn: int) -> dict[int, Move]:
    """The empty cells one pawn can reach, with the move for each: a clone next to it, a jump 2 cells away."""
    if position.ends_game():
        return {}
    cells = position.cells
    targets = {n: Move(n) for n in NEIGHBOURS[pawn] if cells[n] == EMPTY}
    targets.update({t: Move(t, pawn) for t in JUMP_TARGETS[pawn] if cells[t] == EMPTY})
    return targets


def describe(before: Position, move: Move, after: Position) -> str:
    """One line about a move, like "Blue jumped from a7 to c5 and infected 2."."""
    mover = before.to_move
    name = mover.name.title()
    text = f"{name} cloned to {move}" if not move.is_jump else f"{name} jumped from {str(move)[:2]} to {str(move)[2:]}"
    infected = before.pawns(mover.opponent) - after.pawns(mover.opponent)
    if infected:
        text += f" and infected {infected}"
    text += "."
    if after.to_move is mover and not after.ends_game():
        text += f" {mover.opponent.name.title()} cannot move and passes."
    return text


class PlayScreen:
    """One Play game: turns clicks into moves and draws the window."""

    def __init__(self, first: Player = Player.BLUE):
        self.first = first
        self.view = BoardView()
        self.hover: tuple[int, int] | None = None
        self.new_game_button = Button(pygame.Rect(PANEL_X, HEIGHT - 70, 250, 44), "New game (N)")
        self.new_game()

    def new_game(self) -> None:
        self.game = Game(first=self.first)
        self.selected: int | None = None  # the pawn the person clicked, waiting for a target
        self.message = ""
        self.animation: MoveAnimation | None = None

    def handle(self, event: pygame.event.Event):
        """React to one event. Returns the screen to show next (for now, always this one)."""
        if event.type == pygame.MOUSEMOTION:
            self.hover = event.pos
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            cell = cell_at(event.pos)
            if cell is not None:
                self.click(cell)
            elif self.new_game_button.contains(event.pos):
                self.new_game()
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_n:
            self.new_game()
        return self

    def click(self, cell: int) -> None:
        """A click on a cell: pick a pawn, drop it, or move to the cell."""
        position = self.game.position
        if position.ends_game():
            return
        owner = position.cells[cell]
        if owner == position.to_move.value:
            # One of your own pawns: pick it, or drop it if it was already picked.
            if cell == self.selected:
                self.selected = None
            elif cell in movable_pawns(position):
                self.selected = cell
        elif owner == EMPTY and self.selected is not None and cell in reachable(position, self.selected):
            self.play(reachable(position, self.selected)[cell])
        elif owner == EMPTY and position.is_legal(Move(cell)):
            # Clones onto one cell are the same move, whichever pawn it comes from.
            self.play(Move(cell))
        else:
            self.selected = None

    def play(self, move: Move) -> None:
        before = self.game.position
        self.game.play(move)
        self.selected = None
        self.message = describe(before, move, self.game.position)
        self.animation = MoveAnimation(before, move, time.monotonic())

    def update(self) -> None:
        """Called every frame. Nothing to do yet: AI players come in step 3."""

    def status(self) -> str:
        result = self.game.result
        if result is None:
            return f"{self.game.position.to_move.name.title()} to move"
        blue, green = result.score
        if result.winner is None:
            return f"Draw, {blue} to {green}" + (" (fifty-move rule)" if blue + green < 49 and blue and green else "")
        return f"{result.winner.name.title()} wins, {max(blue, green)} to {min(blue, green)}"

    @property
    def wants_hand_cursor(self) -> bool:
        if not self.hover:
            return False
        if self.new_game_button.contains(self.hover):
            return True
        cell = cell_at(self.hover)
        return cell is not None and self._clickable(cell)

    def _clickable(self, cell: int) -> bool:
        position = self.game.position
        if position.ends_game():
            return False
        if self.selected is not None and cell in reachable(position, self.selected):
            return True
        return cell in movable_pawns(position) or (position.cells[cell] == EMPTY and position.is_legal(Move(cell)))

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(BACKGROUND)
        position = self.game.position
        hover_cell = cell_at(self.hover) if self.hover else None
        over = position.ends_game()
        self.view.draw(
            surface,
            position,
            selected=self.selected,
            targets=reachable(position, self.selected) if self.selected is not None else None,
            movable=None if over else movable_pawns(position),
            hover=hover_cell,
            last_move=self.game.moves[-1] if self.game.moves else None,
            animation=self.animation,
        )
        self._draw_panel(surface)
        self.new_game_button.draw(surface, self.view.font_small, self.hover)

    def _draw_panel(self, surface: pygame.Surface) -> None:
        """The side panel: the title, each player's pawns, whose turn it is, the last move, and the list of moves."""
        view, now = self.view, time.monotonic()
        surface.blit(view.font_big.render("Schlurp", True, TEXT), (PANEL_X, 24))
        position = self.game.position
        over = position.ends_game()
        for i, player in enumerate(Player):
            y = 100 + i * 56
            if not over and player is position.to_move:
                pygame.draw.rect(surface, (40, 48, 52), pygame.Rect(PANEL_X - 8, y - 24, 258, 48), border_radius=10)
            view.draw_microbe(surface, (PANEL_X + 18, y), 16, LOOKS[player], now, i)
            surface.blit(view.font.render(player.name.title(), True, TEXT), (PANEL_X + 46, y - 10))
            count = view.font_big.render(str(position.pawns(player)), True, TEXT)
            surface.blit(count, count.get_rect(midright=(PANEL_X + 240, y)))
        surface.blit(view.font.render(self.status(), True, TEXT), (PANEL_X, 196))
        for i, line in enumerate(wrap(self.message, view.font_small, 255)):
            surface.blit(view.font_small.render(line, True, TEXT_SOFT), (PANEL_X, 228 + i * 20))
        self._draw_moves(surface, 300)
        for i, line in enumerate(wrap(HELP, view.font_small, 255)):
            surface.blit(view.font_small.render(line, True, TEXT_SOFT), (PANEL_X, HEIGHT - 160 + i * 20))
        surface.blit(view.font_small.render(KEYS, True, TEXT_SOFT), (PANEL_X, HEIGHT - 100))

    def _draw_moves(self, surface: pygame.Surface, top: int) -> None:
        """The last moves, numbered, each with a dot in the mover's colour."""
        view = self.view
        surface.blit(view.font_small.render("Moves", True, TEXT), (PANEL_X, top))
        first = max(0, len(self.game.moves) - MOVES_SHOWN)
        for row, k in enumerate(range(first, len(self.game.moves))):
            y = top + 28 + row * 20
            mover = self.game.positions[k].to_move  # positions[k] is the position before move k
            surface.blit(view.font_small.render(f"{k + 1}.", True, TEXT_SOFT), (PANEL_X, y))
            pygame.draw.circle(surface, LOOKS[mover].body, (PANEL_X + 48, y + 7), 6)
            surface.blit(view.font_small.render(str(self.game.moves[k]), True, TEXT), (PANEL_X + 62, y))


def wrap(text: str, font: pygame.font.Font, width: int) -> list[str]:
    """Split text into lines no wider than `width` pixels."""
    lines, line = [], ""
    for word in text.split():
        candidate = f"{line} {word}".strip()
        if font.size(candidate)[0] <= width or not line:
            line = candidate
        else:
            lines.append(line)
            line = word
    return lines + [line] if line else lines
