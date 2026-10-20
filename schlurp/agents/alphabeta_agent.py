"""The AlphaBeta agent: looks several moves ahead, expects the opponent's best answer, and skips the lines
that cannot change its choice."""

import math

from schlurp.agents.base import Agent, Thoughts
from schlurp.agents.heuristics import WIN, Heuristic, pawns
from schlurp.engine import Move, Player, Position

DEPTH = 3
INFINITY = math.inf


class SearchStopped(Exception):
    """Raised inside the search when the move is no longer wanted (see Agent.should_stop)."""


class AlphaBetaAgent(Agent):
    """Tries the lines of play `depth` moves deep. On its own turns it takes its best move, on the
    opponent's turns it expects the opponent's best move, which is the worst for itself. The heuristic
    judges the positions where the lines stop.

    This is Minimax. Alpha-beta pruning makes it faster without changing a single choice: as soon as one
    answer shows that a move is worse than one we already have, the other answers to it are skipped.
    """

    name = "AlphaBeta"

    def __init__(self, seed: int | None = None, depth: int = DEPTH, heuristic: Heuristic = pawns):
        super().__init__(seed)
        if depth < 1:
            raise ValueError(f"{self.name} needs a depth of at least 1, not {depth}")
        self.depth = depth
        self.heuristic = heuristic
        self.positions = 0  # counted by the search, and reset for each move

    def think(self, position: Position) -> Thoughts:
        me = position.to_move
        self.positions = 0
        moves = position.legal_moves()
        try:
            # Each of our moves is searched with the widest window, so every move gets its exact score:
            # Watch shows true scores, and a tie between the best moves is broken at random, as in Greedy.
            results = {}
            for move in moves:
                self.positions += 1
                results[move] = self.alphabeta(position.play_legal(move), self.depth - 1, me, -INFINITY, INFINITY)
        except SearchStopped:
            return Thoughts(moves[0], positions=self.positions)  # nobody will play it
        scores = {move: value for move, (value, _) in results.items()}
        best = max(scores.values())
        move = self.rng.choice([move for move, score in scores.items() if score == best])
        return Thoughts(move, scores, (move, *results[move][1]), self.positions, self.depth)

    def alphabeta(
        self, position: Position, depth: int, me: Player, alpha: float, beta: float
    ) -> tuple[float, tuple[Move, ...]]:
        """How good `position` is for `me`, looking `depth` more moves ahead, and the line of play that leads there.

        `alpha` is a value `me` can already get somewhere higher in the tree, and `beta` a value the
        opponent can already hold us to. The game never reaches this position if it is worth alpha or less
        (we would play the other way), or beta or more (the opponent would). So:
        - if the value is between alpha and beta, it is exact, and so is the line;
        - if it is alpha or less, we only learn "alpha or less", and the same for beta or more.
        That is all the positions above need, and it lets us stop early.
        """
        if position.ends_game():
            return self.final_value(position, me, depth), ()
        if depth == 0:
            return self.heuristic(position, me), ()
        if self.should_stop():
            raise SearchStopped
        # After a pass the same player moves again, so we ask whose turn it is instead of taking turns.
        our_turn = position.to_move is me
        best, best_line = (-INFINITY if our_turn else INFINITY), ()
        for move in position.legal_moves():
            self.positions += 1
            value, line = self.alphabeta(position.play_legal(move), depth - 1, me, alpha, beta)
            if our_turn:
                if value > best:
                    best, best_line = value, (move, *line)
                alpha = max(alpha, best)
            else:
                if value < best:
                    best, best_line = value, (move, *line)
                beta = min(beta, best)
            if alpha >= beta:
                # Our turn: we already have a move worth beta or more, and the opponent will not allow it.
                # Their turn: they already have an answer worth alpha or less to us, and we will not allow it.
                # Either way the game never comes here, so the other moves do not matter.
                break
        return best, best_line

    @staticmethod
    def final_value(position: Position, me: Player, depth: int) -> float:
        """The value of a position where the game ends: a win, a loss or a draw, not a guess.

        `depth` is how many moves the search could still look ahead. A win found earlier keeps
        more of it, so a quick win scores higher than a slow one, and a slow loss higher than a quick one.
        """
        winner = position.result().winner
        if winner is None:
            return 0
        return WIN + depth if winner is me else -WIN - depth
