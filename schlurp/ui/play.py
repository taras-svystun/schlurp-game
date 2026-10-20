"""Play: two people share one computer, or a person plays against an AI agent."""

import pygame

from schlurp.agents import Agent, make_agent
from schlurp.engine import EMPTY, JUMP_TARGETS, NEIGHBOURS, Move, Player, Position
from schlurp.ui.agent_thread import AgentThread
from schlurp.ui.board_view import BACKGROUND, HEIGHT, LOOKS, TEXT, TEXT_SOFT, cell_at
from schlurp.ui.game_screen import PANEL_WIDTH, PANEL_X, PERSON, GameScreen, describe, error_words, move_words, wrap
from schlurp.ui.widgets import Button

HELP = "Click a pawn, then a cell. Or click an empty cell next to your pawns to clone there."
KEYS = ("Keys: U undo, N new, M menu,", "H hint, Esc quit")  # two lines, split by hand so no key loses its word
KEYS_TOP = HEIGHT - 112  # the lines about the keys, just above the buttons
MOVES_SHOWN = 10
# An AI's move waits at least this long (seconds) after it starts thinking, so you see your own move land first.
AI_MOVE_DELAY = 0.7
# The agent that suggests a move when the person asks for a hint: the strongest we have that answers in under a second.
# Deepening with `mix` thinks for at most half a second (see docs/agents/deepening.md).
HINT_AGENT = "Deepening:mix"

__all__ = ["PERSON", "PlayScreen", "describe", "movable_pawns", "reachable", "wrap"]


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


class PlayScreen(GameScreen):
    """One Play game: turns clicks into moves, lets AI agents move, and draws the window."""

    def __init__(
        self,
        players: dict[Player, Agent | None] | None = None,
        first: Player = Player.BLUE,
        ai_move_delay: float = AI_MOVE_DELAY,
    ):
        width, gap, top = 60, 5, HEIGHT - 66
        self.undo_button, self.new_game_button, self.menu_button, self.hint_button = (
            Button(pygame.Rect(PANEL_X + i * (width + gap), top, width, 44), label)
            for i, label in enumerate(["Undo", "New", "Menu", "Hint"])
        )
        # Its own agent, never one of the players, so a hint and an AI's move never share an agent.
        self.hint_agent = make_agent(HINT_AGENT)
        self.hint_thinking: AgentThread | None = None  # the hint agent choosing a move for the person
        self.hint: Move | None = None  # the move the hint agent suggests, shown on the board
        super().__init__(players or {Player.BLUE: None, Player.GREEN: None}, first, ai_move_delay)

    def new_game(self) -> None:
        self.drop_hint()
        super().new_game()
        self.selected: int | None = None  # the pawn the person clicked, waiting for a target

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
            elif self.hint_button.contains(event.pos):
                self.ask_hint()
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_u, pygame.K_BACKSPACE):
                self.undo()
            elif event.key == pygame.K_n:
                self.new_game()
            elif event.key == pygame.K_m:
                return self.open_menu()
            elif event.key == pygame.K_h:
                self.ask_hint()
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
        self.selected = None
        self.drop_hint()
        super().play(move)

    def update(self) -> None:
        """Called every frame. Shows a hint once the hint agent has chosen its move, and lets an AI move."""
        if self.hint_thinking and self.hint_thinking.is_done:
            thinking, self.hint_thinking = self.hint_thinking, None
            if thinking.error:
                self.message = f"Hint crashed. {error_words(thinking.error)}"
                return super().update()
            self.hint = thinking.thoughts.move
            self.message = f"Hint from {HINT_AGENT}: {move_words(self.hint)}."
        super().update()

    def undo(self) -> None:
        """Take back moves until a person is to move: one move between two people,
        or back to your last turn against an AI."""
        target = self._undo_target()
        if target is None:
            return
        while len(self.game.moves) > target:
            self.game.undo()
        self.stop_thinking()  # if an AI was thinking, its move is no longer wanted
        self.crashed = None  # a crashed agent gets another try
        self.drop_hint()
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

    @property
    def can_ask_hint(self) -> bool:
        return self.persons_turn and self.hint is None and self.hint_thinking is None

    def ask_hint(self) -> None:
        """Ask the hint agent which move it would play for the person to move. It thinks in its own thread."""
        if self.can_ask_hint:
            self.hint_thinking = AgentThread(self.hint_agent, self.game)

    def drop_hint(self) -> None:
        """Forget the hint, or cancel it if it is still being thought about. Called whenever the position changes."""
        if self.hint_thinking:
            self.hint_thinking.cancel()
            self.hint_thinking = None
        self.hint = None

    def open_menu(self):
        self.drop_hint()
        return super().open_menu()

    @property
    def wants_hand_cursor(self) -> bool:
        if not self.hover:
            return False
        if self.new_game_button.contains(self.hover) or self.menu_button.contains(self.hover):
            return True
        if self.undo_button.contains(self.hover):
            return self._undo_target() is not None
        if self.hint_button.contains(self.hover):
            return self.can_ask_hint
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
            hint=self.hint,
        )
        self.draw_panel_top(surface)
        self._draw_moves(surface, 310)
        self.draw_lines(surface, wrap(HELP, self.view.font_small, PANEL_WIDTH), HEIGHT - 178, spacing=20)
        self.draw_lines(surface, KEYS, KEYS_TOP)
        self.undo_button.draw(surface, self.view.font_small, self.hover, enabled=self._undo_target() is not None)
        self.new_game_button.draw(surface, self.view.font_small, self.hover)
        self.menu_button.draw(surface, self.view.font_small, self.hover)
        self.hint_button.draw(surface, self.view.font_small, self.hover, enabled=self.can_ask_hint)

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
