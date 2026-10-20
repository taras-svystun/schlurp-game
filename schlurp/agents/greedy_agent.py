"""The Greedy agent: looks one move ahead and takes the best pawn difference."""

from schlurp.agents.base import Agent, Thoughts
from schlurp.engine import Position


class GreedyAgent(Agent):
    """Plays the move after which it has the most pawns more than the opponent. Never thinks about the answer."""

    name = "Greedy"

    def think(self, position: Position) -> Thoughts:
        me, enemy = position.to_move, position.to_move.opponent
        scores = {}
        for move in position.legal_moves():
            # Try the move and count. The engine applies the infections, so we only look at the result.
            after = position.play_legal(move)
            scores[move] = after.pawns(me) - after.pawns(enemy)
        best = max(scores.values())
        # Several moves often give the same difference (all clones that infect nobody, say).
        # Greedy has no reason to prefer one, so it picks at random instead of always the first in the list.
        move = self.rng.choice([move for move, score in scores.items() if score == best])
        return Thoughts(move, scores, line=(move,), positions=len(scores), depth=1)
