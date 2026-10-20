"""The game behind the web page. The page sends small messages and gets the new position back.

In the browser this runs in Pyodide, inside a Web Worker (see docs/adr/0005). Messages are dicts that
JSON can carry:

- {"type": "new", "first": "blue"}  start a new game; "first" is "blue" or "green", Blue if left out
- {"type": "play", "move": "a1c3"}  play a move, written like "c3" (a clone) or "a1c3" (a jump)
- {"type": "undo"}                  take back the last move

The answer is always the whole state of the game (see `WebGame.state`), or {"type": "error", "message": ...}
when the message cannot be done. An error never changes the game.
"""

import json

from schlurp.clicks import reachable
from schlurp.engine import CELLS, Game, Move, Player, Position, cell_name

LETTERS = {0: ".", Player.BLUE.value: "B", Player.GREEN.value: "G"}


class WebGame:
    def __init__(self, start: Position | None = None):
        self.game = Game(start=start)

    def handle(self, message: dict) -> dict:
        """Do what the message asks, and return the new state, or an error."""
        kind = message.get("type")
        try:
            if kind == "new":
                first = message.get("first", "blue")
                if first not in ("blue", "green"):
                    return error(f"Who moves first must be blue or green, not {first!r}")
                self.game = Game(Player[first.upper()])
            elif kind == "play":
                move = message.get("move")
                if not isinstance(move, str):
                    return error("A play message needs a move, like 'c3' or 'a1c3'")
                self.game.play(Move.parse(move))
            elif kind == "undo":
                self.game.undo()
            else:
                return error(f"Unknown message type {kind!r}: use new, play or undo")
        except ValueError as problem:
            # The engine's message can end with a picture of the board; the first line says it all.
            return error(str(problem).splitlines()[0])
        return self.state()

    def handle_json(self, text: str) -> str:
        """`handle` for a message written in JSON. This is what the Web Worker calls."""
        try:
            message = json.loads(text)
        except json.JSONDecodeError:
            return json.dumps(error("The message is not JSON"))
        if not isinstance(message, dict):
            return json.dumps(error("The message must be a JSON object"))
        return json.dumps(self.handle(message))

    def state(self) -> dict:
        """Everything the page needs to draw the game.

        - "cells": 49 letters, "." empty, "B" Blue, "G" Green, in the engine's order: a1 first, then b1, ..., g7 last
        - "to_move": "blue" or "green"
        - "pawns": {"blue": 2, "green": 2}
        - "moves": every move so far, like ["f2", "a1c3"]
        - "passed": True if the player who just moved moves again, because the other one could not
        - "reachable": for each pawn that can move, the cells it can reach and the move for each,
          like {"a7": {"b7": "b7", "c7": "a7c7"}}; a clone's move is its target cell, a jump's has both cells
        - "result": None while the game goes on, else {"winner": "blue", "green" or None, "score": [blue, green],
          "ended_by": "no pawns", "full board" or "fifty-move rule"}
        """
        position = self.game.position
        positions = self.game.positions
        moves_from = {}
        for pawn in range(CELLS):
            if position.cells[pawn] == position.to_move.value:
                targets = reachable(position, pawn)
                if targets:
                    moves_from[cell_name(pawn)] = {cell_name(cell): str(move) for cell, move in targets.items()}
        result = position.result()
        return {
            "type": "state",
            "cells": "".join(LETTERS[cell] for cell in position.cells),
            "to_move": position.to_move.name.lower(),
            "pawns": {"blue": position.pawns(Player.BLUE), "green": position.pawns(Player.GREEN)},
            "moves": [str(move) for move in self.game.moves],
            # positions[-2].to_move made the last move; if they are to move again, the other player passed.
            "passed": len(positions) > 1 and not result and positions[-2].to_move == position.to_move,
            "reachable": moves_from,
            "result": result and {
                "winner": result.winner and result.winner.name.lower(),
                "score": list(result.score),
                "ended_by": result.ended_by,
            },
        }


def error(message: str) -> dict:
    return {"type": "error", "message": message}
