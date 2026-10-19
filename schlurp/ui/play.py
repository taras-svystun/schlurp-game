"""Play: two people share one computer, or a person plays against an AI agent."""

import time

import pygame

from schlurp.agents import Agent
from schlurp.engine import EMPTY, JUMP_TARGETS, NEIGHBOURS, Game, Move, Player, Position
from schlurp.records import GameRecord, save_game
from schlurp.ui.agent_thread import AgentThread
from schlurp.ui.board_view import BACKGROUND, HEIGHT, LOOKS, TEXT, TEXT_SOFT, BoardView, MoveAnimation, cell_at
from schlurp.ui.widgets import Button

HELP = "Click a pawn, then a cell. Or click an empty cell next to your pawns to clone there."
KEYS = "Backspace also undoes.   Esc: quit"
PANEL_X = 720  # the side panel, right of the lens
MOVES_SHOWN = 10
# How a person is named in the menu and in game records.
PERSON = "Person"
# An AI's move waits at least this long (seconds) after it starts thinking, so you see your own move land first.
AI_MOVE_DELAY = 0.7


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


class PlayScreen:
    """One Play game: turns clicks into moves, lets AI agents move, and draws the window."""

    def __init__(
        self,
        players: dict[Player, Agent | None] | None = None,
        first: Player = Player.BLUE,
        ai_move_delay: float = AI_MOVE_DELAY,
    ):
        # The AI agent for each player, or None where a person clicks the board.
        self.players = players or {Player.BLUE: None, Player.GREEN: None}
        self.first = first
        self.ai_move_delay = ai_move_delay
        self.view = BoardView()
        self.hover: tuple[int, int] | None = None
        width, gap, top = 80, 5, HEIGHT - 66
        self.undo_button, self.new_game_button, self.menu_button = (
            Button(pygame.Rect(PANEL_X + i * (width + gap), top, width, 44), label)
            for i, label in enumerate(["Undo (U)", "New (N)", "Menu (M)"])
        )
        self.new_game()

    def new_game(self) -> None:
        self.game = Game(first=self.first)
        self.selected: int | None = None  # the pawn the person clicked, waiting for a target
        self.message = ""
        self.animation: MoveAnimation | None = None
        self.thinking: AgentThread | None = None  # the AI agent choosing a move right now

    @property
    def agent_to_move(self) -> Agent | None:
        return self.players[self.game.position.to_move]

    @property
    def persons_turn(self) -> bool:
        """True when a person may click: the game goes on and no AI is to move."""
        return not self.game.is_over and self.agent_to_move is None

    def handle(self, event: pygame.event.Event):
        """React to one event. Returns the screen to show next: this one, or the start menu."""
        if event.type == pygame.MOUSEMOTION:
            self.hover = event.pos
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            cell = cell_at(event.pos)
            if cell is not None:
                self.click(cell)
            elif self.undo_button.contains(event.pos):
                self.undo()
            elif self.new_game_button.contains(event.pos):
                self.new_game()
            elif self.menu_button.contains(event.pos):
                return self.open_menu()
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_u, pygame.K_BACKSPACE):
                self.undo()
            elif event.key == pygame.K_n:
                self.new_game()
            elif event.key == pygame.K_m:
                return self.open_menu()
        return self

    def click(self, cell: int) -> None:
        """A click on a cell: pick a pawn, drop it, or move to the cell."""
        if not self.persons_turn:
            return
        position = self.game.position
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
        names = {player: self.player_name(player) for player in Player}
        self.message = describe(before, move, self.game.position, names)
        self.animation = MoveAnimation(before, move, time.monotonic())
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
        if time.monotonic() - self.thinking.started >= self.ai_move_delay:
            thinking, self.thinking = self.thinking, None
            self.play(thinking.thoughts.move)

    def undo(self) -> None:
        """Take back moves until a person is to move: one move between two people,
        or back to your last turn against an AI."""
        target = self._undo_target()
        if target is None:
            return
        while len(self.game.moves) > target:
            self.game.undo()
        self.thinking = None  # if an AI was thinking, its move is no longer wanted
        self.selected = None
        self.animation = None
        self.message = ""

    def _undo_target(self) -> int | None:
        """How many moves to keep after an undo, or None if there is nothing to undo."""
        people = {player for player, agent in self.players.items() if agent is None}
        positions = self.game.positions
        for moves in range(len(self.game.moves) - 1, -1, -1):
            if positions[moves].to_move in people:
                return moves
        return None

    def open_menu(self):
        from schlurp.ui.menu import MenuScreen  # imported here because the menu imports this file

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

    @property
    def wants_hand_cursor(self) -> bool:
        if not self.hover:
            return False
        if self.new_game_button.contains(self.hover) or self.menu_button.contains(self.hover):
            return True
        if self.undo_button.contains(self.hover):
            return self._undo_target() is not None
        cell = cell_at(self.hover)
        return cell is not None and self._clickable(cell)

    def _clickable(self, cell: int) -> bool:
        if not self.persons_turn:
            return False
        position = self.game.position
        if self.selected is not None and cell in reachable(position, self.selected):
            return True
        return cell in movable_pawns(position) or (position.cells[cell] == EMPTY and position.is_legal(Move(cell)))

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(BACKGROUND)
        position = self.game.position
        persons_turn = self.persons_turn
        self.view.draw(
            surface,
            position,
            selected=self.selected,
            targets=reachable(position, self.selected) if self.selected is not None else None,
            movable=movable_pawns(position) if persons_turn else None,
            hover=cell_at(self.hover) if self.hover and persons_turn else None,
            last_move=self.game.moves[-1] if self.game.moves else None,
            animation=self.animation,
        )
        self._draw_panel(surface)
        self.undo_button.draw(surface, self.view.font_small, self.hover, enabled=self._undo_target() is not None)
        self.new_game_button.draw(surface, self.view.font_small, self.hover)
        self.menu_button.draw(surface, self.view.font_small, self.hover)

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
            surface.blit(view.font.render(self.player_name(player), True, TEXT), (PANEL_X + 46, y - 10))
            count = view.font_big.render(str(position.pawns(player)), True, TEXT)
            surface.blit(count, count.get_rect(midright=(PANEL_X + 240, y)))
        for i, line in enumerate(wrap(self.status(), view.font, 255)):
            surface.blit(view.font.render(line, True, TEXT), (PANEL_X, 190 + i * 24))
        for i, line in enumerate(wrap(self.message, view.font_small, 255)):
            surface.blit(view.font_small.render(line, True, TEXT_SOFT), (PANEL_X, 242 + i * 20))
        self._draw_moves(surface, 310)
        for i, line in enumerate(wrap(HELP, view.font_small, 255)):
            surface.blit(view.font_small.render(line, True, TEXT_SOFT), (PANEL_X, HEIGHT - 160 + i * 20))
        surface.blit(view.font_small.render(KEYS, True, TEXT_SOFT), (PANEL_X, HEIGHT - 96))

    def _draw_moves(self, surface: pygame.Surface, top: int) -> None:
        """The last moves, numbered, each with a dot in the mover's colour."""
        view = self.view
        surface.blit(view.font_small.render("Moves", True, TEXT), (PANEL_X, top))
        first = max(0, len(self.game.moves) - MOVES_SHOWN)
        for row, k in enumerate(range(first, len(self.game.moves))):
            y = top + 26 + row * 18
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
