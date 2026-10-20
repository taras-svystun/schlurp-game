"""Builds the web version and serves it on this computer.

The page in `web/` runs our Python in the browser with Pyodide (see docs/adr/0005). The browser cannot
read our `schlurp/` folder, so `build` packs the files it needs into one zip next to the page, and the
Web Worker unpacks it into Pyodide. Pygame, the window, tournaments and records stay out.

`serve` runs PHP's own small web server, which serves the page and the game server (`web/api.php`)
together, like Apache does on the real site.
"""

import shutil
import socket
import subprocess
import sys
import zipfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
WEB_DIR = PROJECT / "web"
ZIP_PATH = WEB_DIR / "build" / "schlurp.zip"
LOG_PATH = PROJECT / "records" / "web-server.log"
PORT = 8000

# Everything the web version needs, as paths inside schlurp/. The agents come along for play against AI later.
PYTHON_FILES = ("__init__.py", "engine.py", "clicks.py", "web_game.py", "agents/*.py")


def build(zip_path: Path = ZIP_PATH) -> Path:
    """Pack the Python files of the web version into a zip, and return its path."""
    package = PROJECT / "schlurp"
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for pattern in PYTHON_FILES:
            for path in sorted(package.glob(pattern)):
                archive.write(path, Path("schlurp") / path.relative_to(package))
    return zip_path


def lan_address() -> str:
    """This computer's address on the local network, like 192.168.1.20.

    Connecting a UDP socket sends nothing; it only makes the system choose the network card it would use.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            probe.connect(("192.0.2.1", 80))  # an address reserved for examples, never really reached
            return probe.getsockname()[0]
        except OSError:
            return "127.0.0.1"


def serve(port: int = PORT, lan: bool = False) -> None:
    """Build the zip, then serve the page and the game server until Ctrl+C.

    Only this computer can open it, unless `lan` is True: then any computer on the same network can.
    """
    php = shutil.which("php")
    if not php:
        sys.exit("schlurp web needs PHP 7.4 or newer, as the `php` command. See First-time setup in the README.")
    build()
    host = "0.0.0.0" if lan else "localhost"
    address = f"http://{lan_address() if lan else 'localhost'}:{port}"
    print(f"Open {address} in a browser. Press Ctrl+C to stop.")
    if lan:
        print("Open it with this address on this computer too, so the game links you send work on the other one.")
    print(f"The server's log is in {LOG_PATH.relative_to(PROJECT)}.", flush=True)  # before PHP takes over
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    # PHP writes a line for every request, and the page asks every second, so the log goes to a file.
    with open(LOG_PATH, "a") as log:
        try:
            subprocess.run([php, "-S", f"{host}:{port}", "-t", str(WEB_DIR)], stdout=log, stderr=log)
        except KeyboardInterrupt:
            print()
