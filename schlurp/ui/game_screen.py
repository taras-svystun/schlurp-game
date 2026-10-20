"""What Play and Watch share: one game, the agents in it, an AI agent thinking in the background, and the side panel."""

import time

import pygame

from schlurp.agents import Agent
from schlurp.engine import Game, Move, Player, Position
from schlurp.records import GameRecord, save_game
from schlurp.ui.agent_thread import AgentThread
from schlurp.ui.board_view import ANIMATION_SECONDS, LOOKS, TEXT, TEXT_SOFT, BoardView, MoveAnimation

PANEL_X = 720  # the side panel, right of the lens
PANEL_WIDTH = 255
# How a person is named in the menu and in game records.
PERSON = "Person"


def move_words(move: Move) -> str:
    """A move in words, like "clone to b6" or "jump from a7 to c5"."""
    if move.is_jump:
        return f"jump from {str(move)[:2]} to {str(move)[2:]}"
    return f"clone to {move}"


def describe(before: Position, move: Move, after: Position, names: dict[Player, str] | None = None) -> str:
    """One line about a move, like "Blue jumped from a7 to c5 and infected 2."."""
    names = names or {player: player.name.title() for player in Player}
    mover = before.to_move
    if move.is_jump:
        text = f"{names[mover]} jumped from {str(move)[:2]} to {str(move)[2:]}"
    else:
        text = f"{names[mover]} cloned to {move}"
    infected = before.pawns(mover.opponent) - after.pawns(mover.opponent)
    if infected:
        text += f" and infected {infected}"
    text += "."
    if after.to_move is mover and not after.ends_game():
        text += f" {names[mover.opponent]} cannot move and passes."
    return text


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


def fit(text: str, fonts: list[pygame.font.Font], width: int, colour=TEXT) -> pygame.Surface:
    """`text` drawn no wider than `width`: in the first font it fits in, else in the last font, cut short with "..."."""
    for font in fonts:
        if font.size(text)[0] <= width:
            return font.render(text, True, colour)
    font = fonts[-1]
    while text and font.size(text + "...")[0] > width:
        text = text[:-1]
    return font.render(text + "...", True, colour)


class GameScreen:
    """One game on the screen. PlayScreen and WatchScreen add their own buttons, keys and drawing."""

    def __init__(self, players: dict[Player, Agent | None], first: Player, move_delay: float):
        # The AI agent for each player, or None where a person clicks the board.
        self.players = players
        self.first = first
        # How long an AI's move waits (seconds), so people can follow the game. Play and Watch count it differently.
        self.move_delay = move_delay
        self.view = BoardView()
        self.hover: tuple[int, int] | None = None
        self.thinking: AgentThread | None = None  # the AI agent choosing a move right now
        self.new_game()

    def new_game(self) -> None:
        self.stop_thinking()
        self.game = Game(first=self.first)
        self.message = ""
        self.animation: MoveAnimation | None = None

    @property
    def agent_to_move(self) -> Agent | None:
        return self.players[self.game.position.to_move]

    @property
    def animating(self) -> bool:
        return self.animation is not None and self.animation.progress(time.monotonic()) < 1.0

    def update(self) -> None:
        """Called every frame. Starts an AI thinking when it is its turn, and plays its move when it is ready."""
        if self.game.is_over or self.agent_to_move is None:
            return
        if self.thinking is None:
            self.thinking = AgentThread(self.agent_to_move, self.game)
            return
        if not self.thinking.is_done:
            return
        if self.thinking.error:
            raise self.thinking.error
        if self.ready_to_play(self.thinking):
            thinking, self.thinking = self.thinking, None
            self.play(thinking.thoughts.move)

    def ready_to_play(self, thinking: AgentThread) -> bool:
        """The AI has chosen its move. Is it time to play it? Play and Watch wait in different ways."""
        return time.monotonic() - thinking.started >= self.move_delay

    def play(self, move: Move, animation_seconds: float = ANIMATION_SECONDS) -> None:
        before = self.game.position
        self.game.play(move)
        names = {player: self.player_name(player) for player in Player}
        self.message = describe(before, move, self.game.position, names)
        self.animation = MoveAnimation(before, move, time.monotonic(), animation_seconds)
        if self.game.is_over:
            self.save_record()

    def save_record(self) -> None:
        """Save the finished game in records/games. If you undo and finish it again, that is saved too.

        A game from a set-up position (only tests make those) is not saved: its moves alone do not tell the game.
        """
        start = self.game.positions[0]
        if start != Position.start(start.to_move):
            return
        save_game(GameRecord.of(self.game, self.agent_name(Player.BLUE), self.agent_name(Player.GREEN)))

    def stop_thinking(self) -> None:
        """Cancel the AI's move, if one is thinking, and forget it (see docs/adr/0004)."""
        if self.thinking:
            self.thinking.cancel()
            self.thinking = None

    def open_menu(self):
        from schlurp.ui.menu import MenuScreen  # imported here because the menu imports this file

        self.stop_thinking()
        return MenuScreen({player: self.agent_name(player) for player in Player}, self.first)

    def agent_name(self, player: Player) -> str:
        agent = self.players[player]
        return agent.name if agent else PERSON

    def player_name(self, player: Player) -> str:
        agent = self.players[player]
        return f"{player.name.title()} ({agent.name})" if agent else player.name.title()

    def status(self) -> str:
        result = self.game.result
        if result is None:
            to_move = self.player_name(self.game.position.to_move)
            return f"{to_move} is thinking..." if self.agent_to_move else f"{to_move} to move"
        blue, green = result.score
        if result.winner is None:
            return f"Draw, {blue} to {green} ({result.ended_by})"
        return f"{self.player_name(result.winner)} wins, {max(blue, green)} to {min(blue, green)}"

    def draw_panel_top(self, surface: pygame.Surface, title: str = "Schlurp") -> None:
        """The top of the side panel: the title, each player's pawns, whose turn it is and the last move."""
        view, now = self.view, time.monotonic()
        surface.blit(view.font_big.render(title, True, TEXT), (PANEL_X, 24))
        position = self.game.position
        over = position.ends_game()
        for i, player in enumerate(Player):
            y = 100 + i * 56
            if not over and player is position.to_move:
                pygame.draw.rect(surface, (40, 48, 52), pygame.Rect(PANEL_X - 8, y - 24, 258, 48), border_radius=10)
            view.draw_microbe(surface, (PANEL_X + 18, y), 16, LOOKS[player], now, i)
            count = view.font_big.render(str(position.pawns(player)), True, TEXT)
            count_rect = count.get_rect(midright=(PANEL_X + 240, y))
            name = fit(self.player_name(player), [view.font, view.font_small], count_rect.left - 10 - (PANEL_X + 46))
            surface.blit(name, name.get_rect(midleft=(PANEL_X + 46, y)))
            surface.blit(count, count_rect)
        # The status takes at most 2 lines, in a smaller font if a long agent name needs it,
        # and the last move's message comes right under it.
        font = view.font if len(wrap(self.status(), view.font, PANEL_WIDTH)) <= 2 else view.font_small
        y = 190
        for line in wrap(self.status(), font, PANEL_WIDTH):
            surface.blit(font.render(line, True, TEXT), (PANEL_X, y))
            y += font.get_linesize()
        for i, line in enumerate(wrap(self.message, view.font_small, PANEL_WIDTH)):
            surface.blit(view.font_small.render(line, True, TEXT_SOFT), (PANEL_X, y + 4 + i * 18))

    def draw_lines(self, surface: pygame.Surface, lines, top: int, spacing: int = 18) -> None:
        for i, line in enumerate(lines):
            surface.blit(self.view.font_small.render(line, True, TEXT_SOFT), (PANEL_X, top + i * spacing))
