"""Small pieces of the window that are not the board, like buttons."""

from dataclasses import dataclass

import pygame

from schlurp.ui.board_view import HIGHLIGHT, METAL, TEXT, TEXT_SOFT


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
        enabled: bool = True,
    ) -> None:
        fill, border, colour = (METAL[2], METAL[1], TEXT) if enabled else (METAL[3], METAL[2], TEXT_SOFT)
        if enabled and hover and self.contains(hover):
            border = HIGHLIGHT
        pygame.draw.rect(surface, fill, self.rect, border_radius=10)
        pygame.draw.rect(surface, border, self.rect, width=2, border_radius=10)
        image = font.render(self.label, True, colour)
        surface.blit(image, image.get_rect(center=self.rect.center))
