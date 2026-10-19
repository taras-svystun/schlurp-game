"""The start menu: pick who plays Blue and Green, and who moves first."""

import time

import pygame

from schlurp.agents import AGENTS, make_agent
from schlurp.engine import Player
from schlurp.ui.board_view import BACKGROUND, LOOKS, TEXT, TEXT_SOFT, WIDTH, BoardView
from schlurp.ui.play import PERSON, PlayScreen
from schlurp.ui.widgets import Button

ROW_Y = {Player.BLUE: 250, Player.GREEN: 330, "first": 410}
LABEL_RIGHT, OPTIONS_X = 330, 350
OPTION_WIDTH, OPTION_GAP, OPTION_HEIGHT = 120, 8, 48
# The AI agents the menu offers: every agent, with its default settings.
MENU_AGENTS = list(AGENTS)


def option_rect(row, i: int) -> pygame.Rect:
    return pygame.Rect(OPTIONS_X + i * (OPTION_WIDTH + OPTION_GAP), ROW_Y[row] - OPTION_HEIGHT // 2, OPTION_WIDTH, OPTION_HEIGHT)


class MenuScreen:
    def __init__(self, choices: dict[Player, str] | None = None, first: Player = Player.BLUE):
        # For each player, PERSON or the name of an AI agent, like "Random" (see make_agent).
        self.choices = choices or {Player.BLUE: PERSON, Player.GREEN: "Random"}
        self.first = first
        self.hover: tuple[int, int] | None = None
        self.view = BoardView()
        self.font_title = pygame.font.Font(None, 84)
        self.player_buttons = {
            (player, name): Button(option_rect(player, i), name)
            for player in Player
            for i, name in enumerate([PERSON, *MENU_AGENTS])
        }
        self.first_buttons = {player: Button(option_rect("first", i), player.name.title()) for i, player in enumerate(Player)}
        self.start_button = Button(pygame.Rect((WIDTH - 240) // 2, 500, 240, 56), "Start (Enter)")

    @property
    def can_start(self) -> bool:
        """Play needs a person on at least one side. Two AI agents will be Watch (step 6)."""
        return PERSON in self.choices.values()

    def handle(self, event: pygame.event.Event):
        """React to one event. Returns the screen to show next: this menu, or the game once it starts."""
        if event.type == pygame.MOUSEMOTION:
            self.hover = event.pos
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for (player, name), button in self.player_buttons.items():
                if button.contains(event.pos):
                    self.choices[player] = name
            for player, button in self.first_buttons.items():
                if button.contains(event.pos):
                    self.first = player
            if self.start_button.contains(event.pos):
                return self.start()
        elif event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            return self.start()
        return self

    def start(self):
        if not self.can_start:
            return self
        players = {player: None if name == PERSON else make_agent(name) for player, name in self.choices.items()}
        return PlayScreen(players, self.first)

    def update(self) -> None:
        pass  # nothing moves on its own in the menu

    @property
    def wants_hand_cursor(self) -> bool:
        if not self.hover:
            return False
        buttons = [*self.player_buttons.values(), *self.first_buttons.values()]
        if self.can_start:
            buttons.append(self.start_button)
        return any(button.contains(self.hover) for button in buttons)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(BACKGROUND)
        view, now = self.view, time.monotonic()
        view.blit_centered(surface, self.font_title, "Schlurp", TEXT, (WIDTH // 2, 100))
        view.blit_centered(surface, view.font, "The Microscope puzzle from The 7th Guest", TEXT_SOFT, (WIDTH // 2, 160))
        for player in Player:
            y = ROW_Y[player]
            view.draw_microbe(surface, (LABEL_RIGHT - 100, y), 18, LOOKS[player], now, player.value)
            image = view.font.render(player.name.title(), True, TEXT)
            surface.blit(image, image.get_rect(midright=(LABEL_RIGHT, y)))
        image = view.font.render("Moves first", True, TEXT_SOFT)
        surface.blit(image, image.get_rect(midright=(LABEL_RIGHT, ROW_Y["first"])))
        for (player, name), button in self.player_buttons.items():
            button.draw(surface, view.font_small, self.hover, selected=self.choices[player] == name)
        for player, button in self.first_buttons.items():
            button.draw(surface, view.font_small, self.hover, selected=self.first is player)
        self.start_button.draw(surface, view.font, self.hover, enabled=self.can_start)
        if self.can_start:
            note = "With a person on either side, you play."
        else:
            note = "Two AI agents playing each other is Watch, which comes in a later step."
        view.blit_centered(surface, view.font_small, note, TEXT_SOFT, (WIDTH // 2, 590))
