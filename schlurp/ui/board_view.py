"""Where things are on the screen, and how to draw the board under the microscope.

The board sits inside a round lens on the left of the window, with a1 at the bottom left
and g7 at the top right, like the cell names. Pawns are drawn as microbes that wobble a little.
Everything is drawn by Pygame: no images or sounds from outside.
"""

import math
import time
from dataclasses import dataclass

import pygame
import pygame.gfxdraw

from schlurp.engine import CELLS, COLUMNS, EMPTY, NEIGHBOURS, SIZE, Move, Player, Position

WIDTH, HEIGHT = 1000, 700

CELL = 60
BOARD = pygame.Rect(145, 140, CELL * SIZE, CELL * SIZE)
LENS_CENTER = BOARD.center
LENS_RADIUS = 315  # the board's corners are 297 px from the middle, so the whole board is inside
PAWN_RADIUS = 23

BACKGROUND = (12, 15, 20)
LENS_MIDDLE = (52, 66, 60)
LENS_EDGE = (16, 22, 22)
METAL = [(34, 37, 42), (92, 97, 106), (58, 62, 70), (24, 26, 30)]  # the lens ring, from outside in
GRID = (78, 102, 94)
TEXT = (226, 232, 228)
TEXT_SOFT = (140, 156, 150)
HIGHLIGHT = (250, 222, 120)
LAST_MOVE = (240, 150, 80)
DIM = (0, 0, 0, 120)


@dataclass(frozen=True)
class Look:
    """The colours of one player's microbes."""

    body: tuple[int, int, int]
    membrane: tuple[int, int, int]
    nucleus: tuple[int, int, int]


LOOKS = {
    Player.BLUE: Look(body=(66, 142, 236), membrane=(28, 66, 140), nucleus=(176, 216, 255)),
    Player.GREEN: Look(body=(84, 192, 98), membrane=(28, 98, 44), nucleus=(192, 246, 182)),
}

# How long the animation of one move lasts: the pawn lands in the first part, then its neighbours are infected.
ANIMATION_SECONDS = 0.45
LANDING_SHARE = 0.45


def cell_center(cell: int) -> tuple[int, int]:
    """Screen point at the middle of a cell. Row 1 is at the bottom."""
    row, column = divmod(cell, SIZE)
    return BOARD.left + column * CELL + CELL // 2, BOARD.top + (SIZE - 1 - row) * CELL + CELL // 2


def cell_at(point: tuple[int, int]) -> int | None:
    """Which cell is under a screen point, or None if it is off the board."""
    if not BOARD.collidepoint(point):
        return None
    column = (point[0] - BOARD.left) // CELL
    row = SIZE - 1 - (point[1] - BOARD.top) // CELL
    return row * SIZE + column


@dataclass(frozen=True)
class MoveAnimation:
    """A move being shown: the pawn lands (and a jumping pawn leaves its cell), then its neighbours change colour."""

    before: Position
    move: Move
    started: float  # time.monotonic() when the move was played

    def progress(self, now: float) -> float:
        """0.0 when the move was just played, 1.0 when the animation is over."""
        return min(1.0, (now - self.started) / ANIMATION_SECONDS)


def blend(a: tuple[int, int, int], b: tuple[int, int, int], share: float) -> tuple[int, int, int]:
    """The colour `share` of the way from a to b."""
    return tuple(round(x + (y - x) * share) for x, y in zip(a, b))


def blend_looks(a: Look, b: Look, share: float) -> Look:
    return Look(blend(a.body, b.body, share), blend(a.membrane, b.membrane, share), blend(a.nucleus, b.nucleus, share))


def ease(share: float) -> float:
    """Start fast and slow down at the end, so a growing microbe settles softly."""
    return 1 - (1 - share) ** 3


class BoardView:
    def __init__(self):
        self.font_big = pygame.font.Font(None, 40)
        self.font = pygame.font.Font(None, 30)
        self.font_small = pygame.font.Font(None, 24)
        self.lens = self._make_lens()

    def draw(
        self,
        surface: pygame.Surface,
        position: Position,
        selected: int | None = None,
        targets: dict[int, Move] | None = None,
        movable: set[int] | None = None,
        hover: int | None = None,
        last_move: Move | None = None,
        animation: MoveAnimation | None = None,
        now: float | None = None,
        hint: Move | None = None,
    ) -> None:
        """Draw the lens, the board and the pawns.

        `targets` are the cells the selected pawn can reach, with the move for each.
        `movable` are the pawns of the person to move that have a move; their other pawns are dimmed.
        `hint` is a move to suggest to the person, drawn as a pulsing ring (and a line from the pawn, for a jump).
        """
        now = time.monotonic() if now is None else now
        targets = targets or {}
        surface.blit(self.lens, (LENS_CENTER[0] - self.lens.get_width() // 2, LENS_CENTER[1] - self.lens.get_height() // 2))
        self._draw_grid(surface)
        if last_move and not animation:
            self._draw_last_move(surface, last_move)
        progress = animation.progress(now) if animation else 1.0
        if progress >= 1.0:
            animation = None
        for cell in range(CELLS):
            self._draw_cell(surface, position, cell, animation, progress, now)
        if movable is not None:
            for cell in range(CELLS):
                if position.cells[cell] == position.to_move.value and cell not in movable:
                    self._dim(surface, cell)
        if selected is not None:
            pygame.draw.circle(surface, HIGHLIGHT, cell_center(selected), PAWN_RADIUS + 5, width=3)
        for cell, move in targets.items():
            self._draw_target(surface, cell, move.is_jump, LOOKS[position.to_move], hover == cell)
        if hover is not None and hover not in targets and hover != selected and movable and hover in movable:
            pygame.draw.circle(surface, HIGHLIGHT, cell_center(hover), PAWN_RADIUS + 5, width=2)
        if hint is not None:
            self._draw_hint(surface, hint, now)

    def _make_lens(self) -> pygame.Surface:
        """The round field of view with its metal ring. Drawn once, since it never changes."""
        outer = LENS_RADIUS + 30
        lens = pygame.Surface((2 * outer, 2 * outer), pygame.SRCALPHA)
        middle = (outer, outer)
        for radius, colour in zip([outer, outer - 8, outer - 14, outer - 26], METAL):
            pygame.draw.circle(lens, colour, middle, radius)
            pygame.gfxdraw.aacircle(lens, *middle, radius, colour)  # a smooth edge
        # Light in the middle, darker towards the edge, as under a real microscope.
        for radius in range(LENS_RADIUS, 0, -2):
            share = (radius / LENS_RADIUS) ** 2
            pygame.draw.circle(lens, blend(LENS_MIDDLE, LENS_EDGE, share), middle, radius)
        return lens

    def _draw_grid(self, surface: pygame.Surface) -> None:
        for i in range(SIZE + 1):
            x, y = BOARD.left + i * CELL, BOARD.top + i * CELL
            pygame.draw.line(surface, GRID, (x, BOARD.top), (x, BOARD.bottom))
            pygame.draw.line(surface, GRID, (BOARD.left, y), (BOARD.right, y))
        pygame.draw.rect(surface, GRID, BOARD, width=2)
        for i in range(SIZE):
            x = BOARD.left + i * CELL + CELL // 2
            self.blit_centered(surface, self.font_small, COLUMNS[i], TEXT_SOFT, (x, BOARD.bottom + 18))
            y = BOARD.top + (SIZE - 1 - i) * CELL + CELL // 2
            self.blit_centered(surface, self.font_small, str(i + 1), TEXT_SOFT, (BOARD.left - 18, y))

    def _draw_last_move(self, surface: pygame.Surface, move: Move) -> None:
        pygame.draw.circle(surface, LAST_MOVE, cell_center(move.target), PAWN_RADIUS + 5, width=2)
        if move.source is not None:
            pygame.draw.circle(surface, LAST_MOVE, cell_center(move.source), 5)

    def _draw_cell(
        self, surface: pygame.Surface, position: Position, cell: int, animation: MoveAnimation | None, progress: float, now: float
    ) -> None:
        value = position.cells[cell]
        if animation is None:
            if value != EMPTY:
                self.draw_microbe(surface, cell_center(cell), PAWN_RADIUS, LOOKS[Player(value)], now, cell)
            return
        mover = animation.before.to_move
        landing = ease(min(1.0, progress / LANDING_SHARE))
        if cell == animation.move.target:
            self.draw_microbe(surface, cell_center(cell), PAWN_RADIUS * landing, LOOKS[mover], now, cell)
        elif cell == animation.move.source:
            # The jumping pawn shrinks away from the cell it leaves.
            self.draw_microbe(surface, cell_center(cell), PAWN_RADIUS * (1 - landing), LOOKS[mover], now, cell)
        elif animation.before.cells[cell] not in (EMPTY, value) and cell in NEIGHBOURS[animation.move.target]:
            # Infected: the pawn turns from the old colour to the new one after the mover has landed.
            share = ease(max(0.0, (progress - LANDING_SHARE) / (1 - LANDING_SHARE)))
            look = blend_looks(LOOKS[mover.opponent], LOOKS[mover], share)
            self.draw_microbe(surface, cell_center(cell), PAWN_RADIUS * (1 + 0.15 * math.sin(math.pi * share)), look, now, cell)
        elif value != EMPTY:
            self.draw_microbe(surface, cell_center(cell), PAWN_RADIUS, LOOKS[Player(value)], now, cell)

    def draw_microbe(
        self, surface: pygame.Surface, center: tuple[int, int], radius: float, look: Look, now: float, seed: int = 0
    ) -> None:
        """A soft blob with a membrane and a nucleus. It wobbles slowly; `seed` makes each one wobble differently."""
        if radius < 2:
            return
        phase = now * 1.6 + seed * 1.7
        points = []
        for i in range(20):
            angle = 2 * math.pi * i / 20
            r = radius * (1 + 0.06 * math.sin(3 * angle + phase) + 0.04 * math.sin(5 * angle - 1.3 * phase))
            points.append((center[0] + r * math.cos(angle), center[1] + r * math.sin(angle)))
        pygame.gfxdraw.filled_polygon(surface, points, look.membrane)
        pygame.gfxdraw.aapolygon(surface, points, look.membrane)
        inner = [(center[0] + (x - center[0]) * 0.82, center[1] + (y - center[1]) * 0.82) for x, y in points]
        pygame.gfxdraw.filled_polygon(surface, inner, look.body)
        pygame.gfxdraw.aapolygon(surface, inner, look.body)
        nucleus = (round(center[0] - radius * 0.22), round(center[1] - radius * 0.18))
        pygame.gfxdraw.filled_circle(surface, *nucleus, max(1, round(radius * 0.32)), look.nucleus)
        pygame.gfxdraw.aacircle(surface, *nucleus, max(1, round(radius * 0.32)), look.nucleus)

    def _draw_target(self, surface: pygame.Surface, cell: int, is_jump: bool, look: Look, hovered: bool) -> None:
        """A cell the selected pawn can reach: a solid ring for a clone, a dashed ring for a jump."""
        center, radius = cell_center(cell), PAWN_RADIUS - 4
        colour = HIGHLIGHT if hovered else look.nucleus
        if not is_jump:
            pygame.draw.circle(surface, colour, center, radius, width=3)
            return
        for i in range(12):
            start = 2 * math.pi * i / 12
            rect = pygame.Rect(center[0] - radius, center[1] - radius, 2 * radius, 2 * radius)
            pygame.draw.arc(surface, colour, rect, start, start + math.pi / 12, width=3)

    def _draw_hint(self, surface: pygame.Surface, move: Move, now: float) -> None:
        """A suggested move: a ring that pulses on the target cell, and for a jump a line from the pawn that jumps.

        A clone has no pawn to point at: any of your pawns next to the target gives the same move.
        """
        target = cell_center(move.target)
        pulse = 0.5 + 0.5 * math.sin(now * 6)
        if move.source is not None:
            source = cell_center(move.source)
            pygame.draw.line(surface, HIGHLIGHT, source, target, width=3)
            pygame.draw.circle(surface, HIGHLIGHT, source, PAWN_RADIUS + 5, width=3)
        pygame.draw.circle(surface, HIGHLIGHT, target, round(PAWN_RADIUS - 6 + 6 * pulse), width=4)

    def _dim(self, surface: pygame.Surface, cell: int) -> None:
        shade = pygame.Surface((2 * PAWN_RADIUS + 6, 2 * PAWN_RADIUS + 6), pygame.SRCALPHA)
        pygame.draw.circle(shade, DIM, (PAWN_RADIUS + 3, PAWN_RADIUS + 3), PAWN_RADIUS + 3)
        x, y = cell_center(cell)
        surface.blit(shade, (x - PAWN_RADIUS - 3, y - PAWN_RADIUS - 3))

    @staticmethod
    def blit_centered(surface, font, text, color, center) -> None:
        image = font.render(text, True, color)
        surface.blit(image, image.get_rect(center=center))
