"""The web version: the game behind the page, the zip for Pyodide, and the same answers in Pyodide as here."""

import json
import os
import random
import re
import shutil
import subprocess
import sys
import threading
import urllib.request
import zipfile
from pathlib import Path

import pytest

from schlurp import web_build
from schlurp.engine import Game, Player, Position, cell_index
from schlurp.web_game import WebGame

PROJECT = Path(__file__).resolve().parents[1]


def test_a_new_game_shows_the_start():
    state = WebGame().handle({"type": "new"})
    assert state["type"] == "state"
    assert state["cells"][cell_index("a7")] == "B" and state["cells"][cell_index("a1")] == "G"
    assert state["cells"].count(".") == 45
    assert state["to_move"] == "blue"
    assert state["pawns"] == {"blue": 2, "green": 2}
    assert state["moves"] == [] and not state["passed"] and state["result"] is None
    # Blue's corner a7 reaches 3 cells by cloning and 5 by jumping.
    assert state["reachable"]["a7"] == {
        "a6": "a6", "b6": "b6", "b7": "b7",
        "a5": "a7a5", "b5": "a7b5", "c5": "a7c5", "c6": "a7c6", "c7": "a7c7",
    }
    assert set(state["reachable"]) == {"a7", "g1"}


def test_green_can_move_first():
    state = WebGame().handle({"type": "new", "first": "green"})
    assert state["to_move"] == "green"
    assert set(state["reachable"]) == {"a1", "g7"}


def test_a_move_changes_the_state_like_the_engine():
    web = WebGame()
    web.handle({"type": "play", "move": "b6"})
    state = web.handle({"type": "play", "move": "a1a3"})
    game = Game()
    game.play("b6")
    game.play("a1a3")
    assert state["moves"] == ["b6", "a1a3"]
    assert state["cells"] == "".join(".BG"[cell] for cell in game.position.cells)
    assert state["pawns"] == {"blue": game.position.pawns(Player.BLUE), "green": game.position.pawns(Player.GREEN)}


def test_an_illegal_move_is_an_error_and_changes_nothing():
    web = WebGame()
    before = web.state()
    assert web.handle({"type": "play", "move": "d4"}) == {"type": "error", "message": "Blue cannot play d4"}
    assert web.handle({"type": "play", "move": "z9"})["type"] == "error"
    assert web.handle({"type": "play"})["type"] == "error"
    assert web.state() == before


def test_bad_messages_are_errors():
    web = WebGame()
    assert web.handle({"type": "fly"})["type"] == "error"
    assert web.handle({"type": "new", "first": "red"})["type"] == "error"
    assert json.loads(web.handle_json("not json"))["type"] == "error"
    assert json.loads(web.handle_json("[1, 2]"))["type"] == "error"
    assert web.handle({"type": "undo"}) == {"type": "error", "message": "There is no move to undo"}


def test_undo_takes_back_one_move():
    web = WebGame()
    start = web.state()
    web.handle({"type": "play", "move": "b6"})
    assert web.handle({"type": "undo"}) == start


def test_a_pass_is_shown():
    # Green's only pawn is walled in by Blue, and Blue still has empty cells: after Blue's move, Blue moves again.
    start = Position.setup(
        """
        G B B . . . .
        B B B . . . .
        B B B . . . .
        . . . . . . .
        . . . . . . .
        . . . . . . .
        . . . . . . .
        """
    )
    web = WebGame(start)
    state = web.handle({"type": "play", "move": "d7"})
    assert state["to_move"] == "blue" and state["passed"]


def test_the_result_is_shown_at_the_end():
    start = Position.setup(
        """
        B . . . . . .
        . G . . . . .
        . . . . . . .
        . . . . . . .
        . . . . . . .
        . . . . . . .
        . . . . . . .
        """
    )
    state = WebGame(start).handle({"type": "play", "move": "a6"})
    assert state["result"] == {"winner": "blue", "score": [3, 0], "ended_by": "no pawns"}
    assert state["reachable"] == {} and not state["passed"]


def test_the_web_game_never_imports_pygame():
    code = "import sys, schlurp.web_game; sys.exit('pygame' in sys.modules)"
    assert subprocess.run([sys.executable, "-c", code]).returncode == 0


def test_the_zip_holds_only_what_the_browser_needs(tmp_path):
    names = zipfile.ZipFile(web_build.build(tmp_path / "schlurp.zip")).namelist()
    assert "schlurp/engine.py" in names and "schlurp/web_game.py" in names
    assert "schlurp/agents/deepening_agent.py" in names
    assert not [name for name in names if name.startswith("schlurp/ui/") or "__pycache__" in name]


def test_the_zip_works_on_its_own(tmp_path):
    # Unpacked alone, as in Pyodide: no installed schlurp and no Pygame to lean on (-I ignores the user's packages).
    zipfile.ZipFile(web_build.build(tmp_path / "schlurp.zip")).extractall(tmp_path)
    code = (
        "import sys; sys.path.insert(0, '.'); from schlurp.web_game import WebGame; from schlurp.agents import make_agent; "
        "assert WebGame().handle({'type': 'new'})['type'] == 'state'; sys.exit('pygame' in sys.modules)"
    )
    assert subprocess.run([sys.executable, "-I", "-c", code], cwd=tmp_path).returncode == 0


def test_the_page_and_the_tests_use_the_same_pyodide():
    in_tests = json.loads((PROJECT / "package.json").read_text())["devDependencies"]["pyodide"]
    in_page = re.search(r"pyodide/v([\d.]+)/", (PROJECT / "web" / "worker.js").read_text()).group(1)
    assert in_page == in_tests


def test_the_server_serves_the_page_and_the_zip():
    web_build.build()
    server = web_build.make_server(port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        address = f"http://localhost:{server.server_address[1]}"
        with urllib.request.urlopen(f"{address}/") as page:
            assert b"<title>Schlurp</title>" in page.read()
        with urllib.request.urlopen(f"{address}/build/schlurp.zip") as response:
            assert response.headers["Cache-Control"] == "no-cache"
            assert response.read(2) == b"PK"
    finally:
        server.shutdown()
        server.server_close()


def random_messages(seed: int) -> list[dict]:
    """A random game as messages, with some illegal moves, undos and a new game mixed in."""
    rng = random.Random(seed)
    first = rng.choice(["blue", "green"])
    game, messages = Game(Player[first.upper()]), [{"type": "new", "first": first}]
    while not game.is_over and len(messages) < 400:
        roll = rng.random()
        if roll < 0.03:
            messages.append({"type": "play", "move": rng.choice(["d4", "a1a2", "g7"])})
        elif roll < 0.06 and game.moves:
            messages.append({"type": "undo"})
            game.undo()
        else:
            move = rng.choice(game.position.legal_moves())
            messages.append({"type": "play", "move": str(move)})
            game.play(move)
    return messages


def test_pyodide_gives_the_same_answers_as_python(tmp_path):
    # Our Python runs in the browser on Pyodide's Python, a newer version than ours (see docs/adr/0005).
    # Node runs the same Pyodide as the page, so whole games must give the same answers in both.
    if not shutil.which("node") or not (PROJECT / "node_modules" / "pyodide").exists():
        if os.environ.get("CI"):
            pytest.fail("Node and Pyodide must be installed on CI: run npm ci")
        pytest.skip("needs Node and Pyodide: run npm ci")
    games = [random_messages(seed) for seed in range(20)]
    zip_path = web_build.build(tmp_path / "schlurp.zip")
    node = subprocess.run(
        ["node", str(PROJECT / "tests" / "pyodide_game.mjs"), str(zip_path)],
        input=json.dumps(games), capture_output=True, text=True, check=True, timeout=120,
    )
    in_pyodide = json.loads(node.stdout)
    for messages, answers in zip(games, in_pyodide):
        web = WebGame()
        assert answers == [web.handle(message) for message in messages]
