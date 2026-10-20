"""Shared test setup."""

import os
import shutil
import socket
import subprocess
import time
from pathlib import Path

import pytest

from schlurp import records


@pytest.fixture(autouse=True)
def records_in_a_temporary_folder(tmp_path, monkeypatch):
    """Every test saves its game records in its own empty folder, never in the real records/."""
    folder = tmp_path / "records"
    monkeypatch.setattr(records, "RECORDS_DIR", folder)
    return folder


@pytest.fixture(scope="session")
def php_server(tmp_path_factory):
    """The address of PHP's own web server serving web/, like `schlurp web` does, with games in a temporary SQLite file."""
    if not shutil.which("php"):
        if os.environ.get("CI"):
            pytest.fail("PHP must be installed on CI")
        pytest.skip("needs PHP, see First-time setup in the README")
    with socket.socket() as free:
        free.bind(("127.0.0.1", 0))
        port = free.getsockname()[1]
    env = {**os.environ, "SCHLURP_SQLITE": str(tmp_path_factory.mktemp("server") / "games.sqlite")}
    # Several workers, so requests sent at the same moment really run at the same moment.
    env["PHP_CLI_SERVER_WORKERS"] = "4"
    web = Path(__file__).resolve().parents[1] / "web"
    php = subprocess.Popen(
        ["php", "-S", f"127.0.0.1:{port}", "-t", str(web)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    for _ in range(100):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.1).close()
            break
        except OSError:
            time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    php.terminate()
    php.wait()
