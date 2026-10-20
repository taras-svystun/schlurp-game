"""The game server in web/api.php, run by PHP's own small web server, with an SQLite file of its own."""

import json
import os
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.parse
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

WEB_DIR = Path(__file__).resolve().parents[1] / "web"


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    """The address of a running game server, which keeps its games in a temporary SQLite file."""
    if not shutil.which("php"):
        if os.environ.get("CI"):
            pytest.fail("PHP must be installed on CI")
        pytest.skip("needs PHP: brew install php")
    with socket.socket() as free:
        free.bind(("127.0.0.1", 0))
        port = free.getsockname()[1]
    env = {**os.environ, "SCHLURP_SQLITE": str(tmp_path_factory.mktemp("server") / "games.sqlite")}
    # Several workers, so requests sent at the same moment really run at the same moment.
    env["PHP_CLI_SERVER_WORKERS"] = "4"
    php = subprocess.Popen(
        ["php", "-S", f"127.0.0.1:{port}", "-t", str(WEB_DIR)],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    address = f"http://127.0.0.1:{port}/api.php"
    for _ in range(100):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.1).close()
            break
        except OSError:
            time.sleep(0.05)
    yield address
    php.terminate()
    php.wait()


def call(address: str, action: str, body: dict | None = None, method: str | None = None, **query) -> tuple[int, dict]:
    """Send one request; return the HTTP status and the JSON answer."""
    url = f"{address}?{urllib.parse.urlencode({'action': action, **query})}"
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(url, data=data, method=method or ("POST" if body is not None else "GET"))
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def new_game(server: str, first: str = "blue") -> dict:
    status, game = call(server, "create", {"first": first})
    assert status == 200
    return game


def test_a_new_game_has_two_secrets_and_no_moves(server):
    game = new_game(server, "green")
    assert game["first"] == "green" and len(game["game"]) == 16
    assert len(game["secrets"]["blue"]) == 32 and game["secrets"]["blue"] != game["secrets"]["green"]
    assert call(server, "game", game=game["game"]) == (200, {"game": game["game"], "first": "green", "moves": []})


def test_moves_are_stored_in_order_with_their_player(server):
    game = new_game(server)
    blue, green = game["secrets"]["blue"], game["secrets"]["green"]
    assert call(server, "move", {"game": game["game"], "secret": blue, "number": 0, "move": "b6"}) == (200, {"moves": 1})
    assert call(server, "move", {"game": game["game"], "secret": green, "number": 1, "move": "a1a3"}) == (200, {"moves": 2})
    status, state = call(server, "game", game=game["game"])
    assert state["moves"] == [
        {"number": 0, "player": "blue", "move": "b6"},
        {"number": 1, "player": "green", "move": "a1a3"},
    ]
    # A browser that already has the first move asks only for the ones after it.
    status, state = call(server, "game", game=game["game"], after=1)
    assert [move["move"] for move in state["moves"]] == ["a1a3"]


def test_a_secret_tells_which_player_you_are(server):
    game = new_game(server)
    assert call(server, "game", game=game["game"], secret=game["secrets"]["green"])[1]["you"] == "green"
    assert call(server, "game", game=game["game"], secret="nope")[1]["you"] is None


def test_a_wrong_secret_cannot_move(server):
    game, other = new_game(server), new_game(server)
    for secret in ["nope", other["secrets"]["blue"], None]:
        status, answer = call(server, "move", {"game": game["game"], "secret": secret, "number": 0, "move": "b6"})
        assert status == 403 and "secret" in answer["error"]
    assert call(server, "game", game=game["game"])[1]["moves"] == []


def test_an_old_or_skipped_move_number_is_refused(server):
    game = new_game(server)
    move = {"game": game["game"], "secret": game["secrets"]["blue"], "move": "b6"}
    assert call(server, "move", {**move, "number": 1})[0] == 409  # skips number 0
    assert call(server, "move", {**move, "number": 0})[0] == 200
    status, answer = call(server, "move", {**move, "number": 0})  # sent again, maybe after a reload
    assert status == 409 and answer["error"] == "The game has 1 moves, so the next one is number 1"


def test_two_moves_with_the_same_number_at_once_store_one(server):
    game = new_game(server)
    secrets = game["secrets"]
    moves = [{"game": game["game"], "secret": secrets[player], "number": 0, "move": "b6"} for player in ["blue", "green"] * 4]
    with ThreadPoolExecutor(len(moves)) as pool:
        statuses = [status for status, _ in pool.map(lambda body: call(server, "move", body), moves)]
    assert statuses.count(200) == 1 and statuses.count(409) == len(moves) - 1
    assert len(call(server, "game", game=game["game"])[1]["moves"]) == 1


def test_bad_requests_are_refused(server):
    game = new_game(server)
    move = {"game": game["game"], "secret": game["secrets"]["blue"], "number": 0}
    for bad in ["z9", "a1a", "b6; DROP TABLE moves", 7, None]:
        assert call(server, "move", {**move, "move": bad})[0] == 400
    for number in [-1, "0", 1.5, None]:
        assert call(server, "move", {**move, "move": "b6", "number": number})[0] == 400
    assert call(server, "create", {"first": "red"})[0] == 400
    assert call(server, "fly")[0] == 400
    assert call(server, "game", game="nosuchgame")[0] == 404
    assert call(server, "move", {**move, "game": "nosuchgame", "move": "b6"})[0] == 404
    assert call(server, "game", game=game["game"], after="-1")[0] == 400
    assert call(server, "create", method="GET")[0] == 405
    assert call(server, "game", {}, game=game["game"])[0] == 405
    status, answer = call(server, "move", method="POST")  # no body at all
    assert status == 400 and "JSON" in answer["error"]


def test_answers_are_never_cached(server):
    # Browsers ask for the same address every second; a cached answer would hide new moves.
    game = new_game(server)
    with urllib.request.urlopen(f"{server}?action=game&game={game['game']}") as response:
        assert response.headers["Cache-Control"] == "no-store"
        assert response.headers["Content-Type"] == "application/json"
