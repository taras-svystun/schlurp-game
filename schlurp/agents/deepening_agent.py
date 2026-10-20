"""The Deepening agent: AlphaBeta that tries the best moves first, and looks deeper and deeper until its time is up."""

import math
import time

from schlurp.agents.alphabeta_agent import INFINITY, AlphaBetaAgent, SearchStopped
from schlurp.agents.base import Thoughts
from schlurp.agents.heuristics import WIN, Heuristic, pawns
from schlurp.engine import Move, Player, Position

# Seconds per move when neither a depth nor a time is given: quick enough to play against and for Watch.
TIME_LIMIT = 0.5
# A hair below the best score so far. Every heuristic rounds to 6 decimals and a won game is a whole number,
# so two different scores are always at least 0.000001 apart, and nothing lies between best - TIE and best.
TIE = 1e-7
# Each depth takes about 8 to 10 times longer than the one before. A depth started after a fifth of the time
# finished in 1 case out of 71 we measured, so it is not started: the time is better saved.
LAST_START = 1 / 5


class OutOfTime(Exception):
    """Raised deep inside the search when the time is up, to drop the depth it was working on."""


class DeepeningAgent(AlphaBetaAgent):
    """AlphaBeta with three additions.

    - Move ordering: it tries the most promising moves first, so alpha-beta can skip more of the others.
    - Iterative deepening: it searches 1 move deep, then 2, then 3, ... Each search tells the next one
      which moves were best, so the next one tries them first.
    - A time limit: when the time is up, it plays the best move of the deepest search it finished.

    Give it a depth, a time limit, or both, and it stops at whichever comes first.
    With a depth and no time limit it chooses exactly the moves AlphaBeta chooses at that depth, only faster.
    """

    name = "Deepening"

    def __init__(
        self,
        seed: int | None = None,
        depth: int | None = None,
        time_limit: float | None = None,
        heuristic: Heuristic = pawns,
    ):
        super().__init__(seed, heuristic=heuristic)
        if depth is None and time_limit is None:
            time_limit = TIME_LIMIT
        if depth is not None and depth < 1:
            raise ValueError(f"{self.name} needs a depth of at least 1, not {depth}")
        if time_limit is not None and time_limit <= 0:
            raise ValueError(f"{self.name} needs a time limit above 0 seconds, not {time_limit}")
        self.depth = depth  # None: no depth limit, only the time limit stops it
        self.time_limit = time_limit  # seconds per move, or None for no time limit
        # For each position searched so far in this move, the move that was best there.
        self.best_moves: dict[Position, Move] = {}
        self.deadline = math.inf  # the perf_counter() time when the search must stop
        self.reached_horizon = False  # did the search stop anywhere because the depth ran out?

    def think(self, position: Position) -> Thoughts:
        me = position.to_move
        started = time.perf_counter()
        self.positions = 0
        self.best_moves = {}
        done = None  # the deepest search we finished: its depth, scores, upper bounds and lines
        depth = 0
        while self.depth is None or depth < self.depth:
            depth += 1
            # The search 1 move deep always finishes, so there is always a move to play.
            if depth > 1 and self.time_limit is not None:
                self.deadline = started + self.time_limit
            self.reached_horizon = False
            try:
                scores, upper_bounds, lines = self.search(position, depth, me)
            except OutOfTime:
                break
            except SearchStopped:
                return Thoughts(position.legal_moves()[0], positions=self.positions)  # nobody will play it
            finally:
                self.deadline = math.inf
            done = depth, scores, upper_bounds, lines
            # Looking deeper cannot change the choice when every line ended the game before the depth ran out,
            # or when the best move surely wins, or every move surely loses: a deeper search finds the same.
            if not self.reached_horizon or abs(max(scores.values())) >= WIN:
                break
            # With more than a fifth of the time gone, the next depth would not finish (see LAST_START).
            if self.time_limit is not None and time.perf_counter() - started > self.time_limit * LAST_START:
                break
        depth, scores, upper_bounds, lines = done
        best = max(scores.values())
        # The same random choice between equally good moves as AlphaBeta, from the moves in the same order.
        legal = position.legal_moves()
        move = self.rng.choice([move for move in legal if scores[move] == best])
        scores = {move: scores[move] for move in legal}
        return Thoughts(move, scores, lines[move], self.positions, depth, frozenset(upper_bounds))

    def search(
        self, position: Position, depth: int, me: Player
    ) -> tuple[dict[Move, float], set[Move], dict[Move, tuple[Move, ...]]]:
        """Search each of our moves `depth` moves deep.

        AlphaBeta gives every move at the top the widest window, so every move gets its exact score.
        Here the window starts just below the best move so far. A move that is worse gets only an upper bound
        ("this or less"), which is much quicker to prove. A move that is as good as the best or better
        still gets its exact score, so we know every move that ties for the best.

        Returns the score of each move, the moves whose score is only an upper bound, and each move's line.
        """
        scores, upper_bounds, lines = {}, set(), {}
        alpha = -INFINITY
        for move, child in self.ordered_moves(position):
            low = alpha - TIE
            value, line = self.alphabeta(child, depth - 1, me, low, INFINITY)
            scores[move], lines[move] = value, (move, *line)
            if value <= low:
                upper_bounds.add(move)
            if value > alpha:
                alpha = value
                self.best_moves[position] = move
        return scores, upper_bounds, lines

    def alphabeta(
        self, position: Position, depth: int, me: Player, alpha: float, beta: float
    ) -> tuple[float, tuple[Move, ...]]:
        """AlphaBeta's search, with the moves in a better order, a watch on the clock,
        and a note of the best move in each position for the next, deeper search.
        """
        if time.perf_counter() > self.deadline:
            raise OutOfTime
        if self.should_stop():
            raise SearchStopped
        if position.ends_game():
            return self.final_value(position, me, depth), ()
        if depth == 0:
            self.reached_horizon = True
            return self.heuristic(position, me), ()
        our_turn = position.to_move is me
        best, best_line = (-INFINITY if our_turn else INFINITY), ()
        for move, child in self.ordered_moves(position):
            value, line = self.alphabeta(child, depth - 1, me, alpha, beta)
            if our_turn:
                if value > best:
                    best, best_line = value, (move, *line)
                alpha = max(alpha, best)
            else:
                if value < best:
                    best, best_line = value, (move, *line)
                beta = min(beta, best)
            if alpha >= beta:
                break
        self.best_moves[position] = best_line[0]
        return best, best_line

    def ordered_moves(self, position: Position) -> list[tuple[Move, Position]]:
        """The legal moves, each with the position it leads to, the most promising first.

        First the move that was best here in the last, shallower search. Then the moves after which the mover
        has the most pawns, like Greedy would choose. Equally good moves stay in board order.
        """
        mover = position.to_move
        children = [(move, position.play_legal(move)) for move in position.legal_moves()]
        self.positions += len(children)
        # sort keeps the order of equal items, also with reverse=True.
        children.sort(key=lambda child: child[1].pawns(mover) - child[1].pawns(mover.opponent), reverse=True)
        best = self.best_moves.get(position)
        if best is not None:
            children.sort(key=lambda child: child[0] != best)  # False comes before True
        return children
