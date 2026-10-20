"""The zip that installs the web version on a server (`schlurp package`), and the check.php page inside it."""

import json
import re
import urllib.error
import urllib.request
import zipfile

from conftest import php_serving
from schlurp import web_build


def test_the_package_holds_the_site_and_a_french_note(tmp_path):
    archive = zipfile.ZipFile(web_build.package(tmp_path))
    names = set(archive.namelist())
    assert names == {"LISEZ-MOI.txt", "schlurp/build/schlurp.zip", "schlurp/version.txt"} | {
        f"schlurp/{name}" for name in web_build.SITE_FILES
    }
    note = archive.read("LISEZ-MOI.txt").decode("utf-8")
    # For Windows: a BOM so every editor reads it as UTF-8, and Windows line ends.
    assert note.startswith("﻿") and "\r\n" in note and "\n" not in note.replace("\r\n", "")
    assert web_build.version() in note and "{version}" not in note
    assert "vérification" in note


def test_the_package_never_holds_the_server_secrets(tmp_path, monkeypatch):
    # A web/ folder that has a config.php and a database, as on a laptop that tried MariaDB.
    web = tmp_path / "web"
    for name in web_build.SITE_FILES:
        (web / name).parent.mkdir(parents=True, exist_ok=True)
        (web / name).write_text((web_build.WEB_DIR / name).read_text())
    (web / "config.php").write_text("<?php $password = 'secret';")
    (web / "data" / "games.sqlite").write_text("games")
    monkeypatch.setattr(web_build, "WEB_DIR", web)
    names = zipfile.ZipFile(web_build.package(tmp_path / "dist")).namelist()
    assert not [name for name in names if name.endswith(("config.php", ".sqlite"))]


def test_the_unpacked_package_runs_and_checks_itself(tmp_path):
    zipfile.ZipFile(web_build.package(tmp_path)).extractall(tmp_path)
    site = tmp_path / "schlurp"
    # The database goes into the site's own data/ folder, as on a server.
    with php_serving(site, site / "data" / "games.sqlite") as address:
        with urllib.request.urlopen(f"{address}/") as page:
            assert b"<title>Schlurp</title>" in page.read()
        request = urllib.request.Request(f"{address}/api.php?action=create", data=json.dumps({"first": "blue"}).encode())
        with urllib.request.urlopen(request) as response:
            assert len(json.loads(response.read())["game"]) == 16
        with urllib.request.urlopen(f"{address}/check.php") as response:
            check = response.read().decode()
        server_checks = dict(re.findall(r'data-check="(\w+)" data-ok="(\w+)"', check))
        assert {name: ok for name, ok in server_checks.items() if ok != "wait"} == {
            "php": "yes", "json": "yes", "random": "yes", "pdo": "yes", "writable": "yes", "database": "yes",
        }
        assert web_build.version() in check
        # The database and check.php's probe file must stay out of the browser's reach.
        for secret in ["data/games.sqlite", "data/probe.txt"]:
            try:
                urllib.request.urlopen(f"{address}/{secret}")
                raise AssertionError(f"{secret} can be downloaded")
            except urllib.error.HTTPError as error:
                assert error.code == 403
