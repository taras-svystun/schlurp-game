"""Builds the web version and serves it on this computer.

The page in `web/` runs our Python in the browser with Pyodide (see docs/adr/0005). The browser cannot
read our `schlurp/` folder, so `build` packs the files it needs into one zip next to the page, and the
Web Worker unpacks it into Pyodide. Pygame, the window, tournaments and records stay out.
"""

import functools
import http.server
import zipfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
WEB_DIR = PROJECT / "web"
ZIP_PATH = WEB_DIR / "build" / "schlurp.zip"
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


def make_server(port: int = PORT, host: str = "localhost") -> http.server.ThreadingHTTPServer:
    """A web server for the `web/` folder. Port 0 picks a free port (for tests)."""
    handler = functools.partial(QuietHandler, directory=str(WEB_DIR))
    return http.server.ThreadingHTTPServer((host, port), handler)


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    """Serves files, and tells the browser to check for a new version every time, so a rebuilt zip is never stale."""

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, format: str, *args) -> None:
        pass  # one line per file would hide the address we print


def serve(port: int = PORT) -> None:
    """Build the zip, then serve the page until Ctrl+C."""
    build()
    server = make_server(port)
    print(f"Open http://localhost:{server.server_address[1]} in a browser. Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()
