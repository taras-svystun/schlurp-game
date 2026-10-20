"""The game behind the web page. The page sends small messages and gets the new position back.

In the browser this runs in Pyodide, inside a Web Worker (see docs/adr/0005). Messages are dicts that
JSON can carry:

- {"type": "new", "first": "blue"}  start a new game; "first" is "blue" or "green", Blue if left out
- {"type": "play", "move": "a1c3"}  play a move, written like "c3" (a clone) or "a1c3" (a jump)
- {"type": "undo"}                  take back the last move

In an online game the moves come from the game server, which does not know the rules, so they also
say who sent them, and a move from the player who is not to move is an error:

- {"type": "play", "move": "a1c3", "player": "green"}
- {"type": "new", "first": "blue", "moves": [{"move": "b6", "player": "blue"}, ...]}
  a new game with these moves already played, for a page that opens or reloads an online game

The answer is always the whole state of the game (see `WebGame.state`), or {"type": "error", "message": ...}
when the message cannot be done. An error never changes the game.
"""

import json

from schlurp.clicks import reachable
from schlurp.engine import CELLS, Game, Move, Player, Position, cell_name

PLAYERS = ("blue", "green")
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
                if first not in PLAYERS:
                    return error(f"Who moves first must be blue or green, not {first!r}")
                moves = message.get("moves", [])
                if not isinstance(moves, list):
                    return error("The moves of a new game must be a list")
                game = Game(Player[first.upper()])
                for number, played in enumerate(moves):
                    problem = play(game, played)
                    if problem:
                        return error(f"Move {number + 1}: {problem}")
                self.game = game  # only now, so a bad move in the list changes nothing
            elif kind == "play":
                problem = play(self.game, message)
                if problem:
                    return error(problem)
            elif kind == "undo":
                self.game.undo()
            else:
                return error(f"Unknown message type {kind!r}: use new, play or undo")
        except ValueError as problem:
            return error(str(problem))
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


def play(game: Game, played) -> str | None:
    """Play one move, given as {"move": "a1c3"} with maybe a "player": "blue". Return what was wrong, or None."""
    if not isinstance(played, dict) or not isinstance(played.get("move"), str):
        return "A move must be given like {'move': 'c3'} or {'move': 'a1c3'}"
    player = played.get("player")
    if player is not None and player != game.position.to_move.name.lower():
        return f"It is not {str(player).title()}'s turn"
    try:
        game.play(Move.parse(played["move"]))
    except ValueError as problem:
        # The engine's message can end with a picture of the board; the first line says it all.
        return str(problem).splitlines()[0]
    return None


def error(message: str) -> dict:
    return {"type": "error", "message": message}
