"""The window's main loop. It shows one screen at a time."""

from collections.abc import Callable

import pygame

from schlurp.ui.board_view import HEIGHT, WIDTH


def run(first_screen: Callable | None = None) -> None:
    """Open the window. `first_screen` makes the screen to show first; by default it is a Play game.

    It is a function, not a screen, because a screen needs Pygame to be started before it is made.
    """
    from schlurp.ui.play import PlayScreen  # imported here so the screens can import this file's neighbours

    pygame.init()
    pygame.display.set_caption("Schlurp")
    surface = pygame.display.set_mode((WIDTH, HEIGHT))
    screen = first_screen() if first_screen else PlayScreen()
    clock = pygame.time.Clock()
    hand_cursor = False
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                pygame.quit()
                return
            screen = screen.handle(event)
        screen.update()
        if screen.wants_hand_cursor != hand_cursor:
            hand_cursor = screen.wants_hand_cursor
            pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND if hand_cursor else pygame.SYSTEM_CURSOR_ARROW)
        screen.draw(surface)
        pygame.display.flip()
        clock.tick(30)
