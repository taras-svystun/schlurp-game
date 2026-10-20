"""The thoughts panel of Watch: what an AI agent shows about how it chose its move.

It has a checkbox for each part:
- move scores, drawn on the board: each empty cell shows the best score of the moves landing there,
  and the chosen move is yellow, with a line from the pawn for a jump; "≤" marks a score that is only an
  upper bound (Deepening proves only that such a move is worse than its best one);
- the expected line of play, in move names like "d4 a1c2";
  MCTS's scores are its share of wins in random games, from 0.00 to 1.00;
- the work done: random games played to the end (MCTS), positions looked at, how deep, and how long it took.
"""

import time

import pygame

from schlurp.agents import Thoughts
from schlurp.tournament import duration
from schlurp.ui.agent_thread import AgentThread
from schlurp.ui.board_view import BACKGROUND, HIGHLIGHT, METAL, PAWN_RADIUS, TEXT, TEXT_SOFT, cell_center
from schlurp.ui.game_screen import PANEL_WIDTH, PANEL_X, wrap
from schlurp.ui.widgets import Checkbox

BADGE_WIDTH, BADGE_HEIGHT = 44, 22


def score_text(score: float, upper_bound: bool = False, share: bool = False) -> str:
    """+3, -2 and 0 for whole numbers (like pawns), 0.25 for the rest. An upper bound gets a "≤" in front.

    A `share` of wins (from MCTS) always has 2 decimals, from 0.00 to 1.00.
    """
    if share:
        text = f"{score:.2f}"
    elif float(score).is_integer():
        text = f"{score:+.0f}" if score else "0"
    else:
        text = f"{score:.2f}"
    return f"≤{text}" if upper_bound else text


def scores_by_cell(thoughts: Thoughts) -> dict[int, tuple[float, bool]]:
    """The best score of the moves landing on each cell, and whether it is only an upper bound.

    One clone and several jumps can land on the same cell, and a cell has room for one number.
    The best one is what matters: it is the move the agent would play to get there.
    """
    best: dict[int, tuple[float, bool]] = {}
    for move, score in thoughts.scores.items():
        if move.target not in best or score > best[move.target][0]:
            best[move.target] = (score, move in thoughts.upper_bounds)
    return best


def work_text(thoughts: Thoughts, seconds: float) -> str:
    if not thoughts.positions:
        return f"no search, {duration(seconds)}"
    playouts = f"{thoughts.playouts:,} playouts, " if thoughts.playouts else ""
    return f"{playouts}{thoughts.positions:,} positions, depth {thoughts.depth}, {duration(seconds)}"


class ThoughtsPanel:
    def __init__(self, top: int):
        self.top = top
        labels = ["Move scores (on the board)", "Expected line", "Work done"]
        self.scores_box, self.line_box, self.work_box = (
            Checkbox(pygame.Rect(PANEL_X, top + i * 28, PANEL_WIDTH, 24), label) for i, label in enumerate(labels)
        )
        self.font = pygame.font.Font(None, 24)
        self.text_top = top + 3 * 28 + 6

    @property
    def checkboxes(self) -> list[Checkbox]:
        return [self.scores_box, self.line_box, self.work_box]

    def handle_click(self, point: tuple[int, int]) -> None:
        for box in self.checkboxes:
            box.handle_click(point)

    def draw(
        self, surface: pygame.Surface, thinking: AgentThread | None, agent_name: str, hover=None, board: bool = True
    ) -> None:
        """Draw the checkboxes, and the parts of `thinking`'s thoughts that are checked.

        `thinking` is the agent choosing a move in the position on the board, or None when nobody is.
        With `board=False` the move scores are not drawn on the board (a move is still landing there).
        """
        for box in self.checkboxes:
            box.draw(surface, self.font, hover)
        if thinking is None:
            return
        lines = []
        if not thinking.is_done:
            if self.work_box.checked:
                waited = time.monotonic() - thinking.started
                lines.append(f"Work done: thinking for {duration(waited)}...")
            self._text(surface, lines)
            return
        thoughts = thinking.thoughts
        if self.scores_box.checked:
            if not thoughts.scores:
                lines.append(f"{agent_name} gives no move scores.")
            elif board:
                self.draw_scores(surface, thoughts)
        if self.line_box.checked:
            line = " ".join(str(move) for move in thoughts.line) if thoughts.line else f"{agent_name} does not give one"
            lines.append(f"Expected line: {line}")
        if self.work_box.checked:
            lines.append(f"Work done: {work_text(thoughts, thinking.seconds)}")
        self._text(surface, lines)

    def draw_scores(self, surface: pygame.Surface, thoughts: Thoughts) -> None:
        chosen = thoughts.move
        if chosen.source is not None:
            # A jump: show which pawn jumps, as the hint does in Play.
            pygame.draw.line(surface, HIGHLIGHT, cell_center(chosen.source), cell_center(chosen.target), width=3)
            pygame.draw.circle(surface, HIGHLIGHT, cell_center(chosen.source), PAWN_RADIUS + 5, width=3)
        for cell, (score, upper_bound) in scores_by_cell(thoughts).items():
            is_chosen = cell == chosen.target
            badge = pygame.Rect(0, 0, BADGE_WIDTH, BADGE_HEIGHT)
            badge.center = cell_center(cell)
            pygame.draw.rect(surface, HIGHLIGHT if is_chosen else METAL[3], badge, border_radius=BADGE_HEIGHT // 2)
            if not is_chosen:
                pygame.draw.rect(surface, METAL[1], badge, width=1, border_radius=BADGE_HEIGHT // 2)
            text = score_text(score, upper_bound, share=thoughts.playouts > 0)
            image = self.font.render(text, True, BACKGROUND if is_chosen else TEXT)
            surface.blit(image, image.get_rect(center=badge.center))

    def _text(self, surface: pygame.Surface, paragraphs: list[str]) -> None:
        y = self.text_top
        for paragraph in paragraphs:
            for line in wrap(paragraph, self.font, PANEL_WIDTH):
                surface.blit(self.font.render(line, True, TEXT_SOFT), (PANEL_X, y))
                y += 20
            y += 4
