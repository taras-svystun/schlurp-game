"""Builds the web version and serves it on this computer.

The page in `web/` runs our Python in the browser with Pyodide (see docs/adr/0005). The browser cannot
read our `schlurp/` folder, so `build` packs the files it needs into one zip next to the page, and the
Web Worker unpacks it into Pyodide. Pygame, the window, tournaments and records stay out.

`serve` runs PHP's own small web server, which serves the page and the game server (`web/api.php`)
together, like Apache does on the real site.
"""

import datetime
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
ROUTER = Path(__file__).resolve().parent / "web_router.php"  # keeps data/ and config.php away from browsers
DIST_DIR = PROJECT / "dist"
PORT = 8000

# What `package` puts on a server, as paths inside web/. Never config.php or the database: they are the server's own.
SITE_FILES = (
    "index.html", "page.js", "board.js", "worker.js", "style.css",
    "api.php", "database.php", "check.php", "config.example.php", "data/.htaccess", "data/index.html",
)
INSTALL_NOTE = PROJECT / "docs" / "install" / "LISEZ-MOI.txt"

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


def version() -> str:
    """Today's date and the git commit, like "2026-10-20 (16959d9)", so we know which version a server runs."""
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=PROJECT, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        commit = "unknown"
    return f"{datetime.date.today()} ({commit})"


def package(dist_dir: Path = DIST_DIR) -> Path:
    """One zip to install the web version on a server: the folder `schlurp/` to upload, and a note in French.

    Pascal installs it himself, from Windows, so the note is plain text with Windows line ends and a BOM,
    which every Windows editor reads as UTF-8.
    """
    built = version()
    dist_dir.mkdir(parents=True, exist_ok=True)
    zip_path = dist_dir / f"schlurp-web-{built.split()[0]}.zip"
    note = INSTALL_NOTE.read_text(encoding="utf-8").replace("{version}", built)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("LISEZ-MOI.txt", "\ufeff" + note.replace("\n", "\r\n"))
        for name in SITE_FILES:
            archive.write(WEB_DIR / name, f"schlurp/{name}")
        archive.write(build(), "schlurp/build/schlurp.zip")
        archive.writestr("schlurp/version.txt", built + "\n")
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
            subprocess.run([php, "-S", f"{host}:{port}", "-t", str(WEB_DIR), str(ROUTER)], stdout=log, stderr=log)
        except KeyboardInterrupt:
            print()
