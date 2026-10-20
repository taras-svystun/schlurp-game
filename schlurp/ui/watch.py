"""Watch: two AI agents play each other, move by move, with their thoughts on and next to the board."""

import math
import time

import pygame

from schlurp.agents import Agent
from schlurp.engine import Move, Player
from schlurp.ui.agent_thread import AgentThread
from schlurp.ui.board_view import ANIMATION_SECONDS, BACKGROUND, HEIGHT, TEXT, TEXT_SOFT
from schlurp.ui.game_screen import PANEL_WIDTH, PANEL_X, GameScreen
from schlurp.ui.thoughts_view import ThoughtsPanel
from schlurp.ui.widgets import Button, Slider

# The speed slider goes from SLOWEST seconds per move at its left end to FASTEST at its right end.
# It is how long an agent's thoughts stay on the board before its move is played.
SLOWEST, FASTEST = 5.0, 0.05
DEFAULT_DELAY = 1.0
CONTROLS_TOP = 306  # the Pause and Step buttons, under the last move's message
SPEED_Y = 382  # the speed slider
THOUGHTS_TOP = 408  # the thoughts checkboxes, with the thoughts below them


def delay_at(value: float) -> float:
    """Seconds per move for a slider value from 0 to 1.

    Each step along the slider multiplies the speed by the same amount (like a volume knob),
    so going from 4 s to 2 s takes as much of the slider as going from 0.1 s to 0.05 s.
    """
    return SLOWEST * (FASTEST / SLOWEST) ** value


def value_for(delay: float) -> float:
    """The opposite of `delay_at`: where the slider sits for `delay` seconds per move."""
    delay = min(SLOWEST, max(FASTEST, delay))
    return math.log(delay / SLOWEST) / math.log(FASTEST / SLOWEST)


class WatchScreen(GameScreen):
    """One Watch game. It shows each agent's thoughts on the position before it plays its move."""

    def __init__(self, players: dict[Player, Agent], first: Player = Player.BLUE, delay: float = DEFAULT_DELAY):
        if None in players.values():
            raise ValueError("Watch needs an AI agent for both players. A game with a person is Play.")
        if players[Player.BLUE] is players[Player.GREEN]:
            raise ValueError("Watch needs two agent objects, even for the same kind of agent: each keeps its own random generator")
        self.paused = False
        self.step_asked = False  # play the next move as soon as it is chosen, even while paused
        half = (PANEL_WIDTH - 5) // 2
        self.pause_button = Button(pygame.Rect(PANEL_X, CONTROLS_TOP, half, 40), "Pause (P)")
        self.step_button = Button(pygame.Rect(PANEL_X + half + 5, CONTROLS_TOP, half, 40), "Step (S)")
        self.speed = Slider(pygame.Rect(PANEL_X + 10, SPEED_Y, PANEL_WIDTH - 20, 6), value_for(delay))
        self.thoughts = ThoughtsPanel(top=THOUGHTS_TOP)
        self.new_game_button = Button(pygame.Rect(PANEL_X, HEIGHT - 66, half, 44), "New (N)")
        self.menu_button = Button(pygame.Rect(PANEL_X + half + 5, HEIGHT - 66, half, 44), "Menu (M)")
        super().__init__(players, first, delay)

    def new_game(self) -> None:
        super().new_game()
        self.step_asked = False

    def handle(self, event: pygame.event.Event):
        """React to one event. Returns the screen to show next: this one, or the start menu."""
        speed_before = self.speed.value
        self.speed.handle(event)
        if self.speed.value != speed_before:
            self.move_delay = delay_at(self.speed.value)
        if event.type == pygame.MOUSEMOTION:
            self.hover = event.pos
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.thoughts.handle_click(event.pos)
            if self.pause_button.contains(event.pos):
                self.toggle_pause()
            elif self.step_button.contains(event.pos):
                self.step()
            elif self.new_game_button.contains(event.pos):
                self.new_game()
            elif self.menu_button.contains(event.pos):
                return self.open_menu()
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_SPACE, pygame.K_p):
                self.toggle_pause()
            elif event.key in (pygame.K_s, pygame.K_RIGHT):
                self.step()
            elif event.key == pygame.K_n:
                self.new_game()
            elif event.key == pygame.K_m:
                return self.open_menu()
        return self

    def toggle_pause(self) -> None:
        self.paused = not self.paused
        self.step_asked = False

    def step(self) -> None:
        """Pause, and play just the next move."""
        self.paused = True
        self.step_asked = True

    def ready_to_play(self, thinking: AgentThread) -> bool:
        if self.step_asked:
            return True
        if self.paused:
            return False
        # The thoughts appear when the agent is done and the last move has landed. They stay on the
        # board for `move_delay` seconds, however long the agent took to think.
        landed = self.animation.started + self.animation.seconds if self.animation else 0.0
        return time.monotonic() - max(thinking.finished, landed) >= self.move_delay

    def play(self, move: Move) -> None:
        # At high speed the animation gets shorter too, so moves do not pile up waiting for it.
        super().play(move, min(ANIMATION_SECONDS, self.move_delay))
        self.step_asked = False

    def status(self) -> str:
        if self.game.is_over or self.crashed:
            return super().status()
        player = self.player_name(self.game.position.to_move)
        if self.thinking and self.thinking.is_done:
            text = f"{player} chose {self.thinking.thoughts.move}"
        else:
            text = f"{player} is thinking..."
        return f"Paused. {text}" if self.paused else text

    @property
    def buttons(self) -> list[Button]:
        return [self.pause_button, self.step_button, self.new_game_button, self.menu_button]

    @property
    def wants_hand_cursor(self) -> bool:
        if not self.hover:
            return False
        return any(item.contains(self.hover) for item in [*self.buttons, *self.thoughts.checkboxes, self.speed])

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(BACKGROUND)
        self.view.draw(
            surface,
            self.game.position,
            last_move=self.game.moves[-1] if self.game.moves else None,
            animation=self.animation,
        )
        self.draw_panel_top(surface, "Schlurp: Watch")
        font = self.view.font_small
        self.pause_button.label = "Resume (P)" if self.paused else "Pause (P)"
        self.pause_button.draw(surface, font, self.hover, selected=self.paused)
        self.step_button.draw(surface, font, self.hover)
        speed = font.render("Speed", True, TEXT)
        surface.blit(speed, speed.get_rect(bottomleft=(PANEL_X, SPEED_Y - 10)))
        per_move = font.render(f"{self.move_delay:.2g} s per move", True, TEXT_SOFT)
        surface.blit(per_move, per_move.get_rect(bottomright=(PANEL_X + PANEL_WIDTH, SPEED_Y - 10)))
        self.speed.draw(surface, self.hover)
        mover = self.game.position.to_move
        self.thoughts.draw(surface, self.thinking, self.agent_name(mover), self.hover, board=not self.animating)
        self.new_game_button.draw(surface, font, self.hover)
        self.menu_button.draw(surface, font, self.hover)
