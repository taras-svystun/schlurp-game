"""Small pieces of the window that are not the board, like buttons."""

from dataclasses import dataclass

import pygame

from schlurp.ui.board_view import BACKGROUND, HIGHLIGHT, METAL, TEXT, TEXT_SOFT


@dataclass
class Button:
    rect: pygame.Rect
    label: str

    def contains(self, point: tuple[int, int]) -> bool:
        return self.rect.collidepoint(point)

    def draw(
        self,
        surface: pygame.Surface,
        font: pygame.font.Font,
        hover: tuple[int, int] | None = None,
        selected: bool = False,
        enabled: bool = True,
    ) -> None:
        if not enabled:
            fill, border, colour = METAL[3], METAL[2], TEXT_SOFT
        elif selected:
            fill, border, colour = HIGHLIGHT, HIGHLIGHT, BACKGROUND
        else:
            fill, border, colour = METAL[2], METAL[1], TEXT
        if enabled and hover and self.contains(hover):
            border = HIGHLIGHT
        pygame.draw.rect(surface, fill, self.rect, border_radius=10)
        pygame.draw.rect(surface, border, self.rect, width=2, border_radius=10)
        image = font.render(self.label, True, colour)
        surface.blit(image, image.get_rect(center=self.rect.center))


@dataclass
class Checkbox:
    """A box you click to turn something on or off. The whole row, label included, can be clicked."""

    rect: pygame.Rect
    label: str
    checked: bool = True
    BOX = 20

    def contains(self, point: tuple[int, int]) -> bool:
        return self.rect.collidepoint(point)

    def handle_click(self, point: tuple[int, int]) -> None:
        if self.contains(point):
            self.checked = not self.checked

    def draw(self, surface: pygame.Surface, font: pygame.font.Font, hover: tuple[int, int] | None = None) -> None:
        box = pygame.Rect(self.rect.left, self.rect.centery - self.BOX // 2, self.BOX, self.BOX)
        if self.checked:
            pygame.draw.rect(surface, HIGHLIGHT, box, border_radius=4)
            tick = [(box.left + 4, box.centery), (box.left + 8, box.bottom - 5), (box.right - 4, box.top + 5)]
            pygame.draw.lines(surface, BACKGROUND, False, tick, width=3)
        border = HIGHLIGHT if hover and self.contains(hover) else TEXT_SOFT
        pygame.draw.rect(surface, border, box, width=2, border_radius=4)
        image = font.render(self.label, True, TEXT)
        surface.blit(image, image.get_rect(midleft=(box.right + 10, box.centery)))


@dataclass
class Slider:
    """A knob you drag along a line. `value` goes from 0.0 at the left end to 1.0 at the right end."""

    rect: pygame.Rect
    value: float = 0.5
    dragging: bool = False
    KNOB = 10

    def contains(self, point: tuple[int, int]) -> bool:
        # A little taller than the line itself, so it is easy to grab.
        return self.rect.inflate(2 * self.KNOB, 2 * self.KNOB).collidepoint(point)

    def handle(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.contains(event.pos):
            self.dragging = True
            self._move_to(event.pos[0])
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            self._move_to(event.pos[0])
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = False

    def _move_to(self, x: int) -> None:
        self.value = min(1.0, max(0.0, (x - self.rect.left) / self.rect.width))

    def draw(self, surface: pygame.Surface, hover: tuple[int, int] | None = None) -> None:
        pygame.draw.line(surface, METAL[3], self.rect.midleft, self.rect.midright, width=6)
        knob_x = self.rect.left + round(self.value * self.rect.width)
        pygame.draw.line(surface, METAL[1], self.rect.midleft, (knob_x, self.rect.centery), width=6)
        active = self.dragging or (hover and self.contains(hover))
        pygame.draw.circle(surface, HIGHLIGHT if active else TEXT, (knob_x, self.rect.centery), self.KNOB)
