"""Shared test setup."""

import pytest

from schlurp import records


@pytest.fixture(autouse=True)
def records_in_a_temporary_folder(tmp_path, monkeypatch):
    """Every test saves its game records in its own empty folder, never in the real records/."""
    folder = tmp_path / "records"
    monkeypatch.setattr(records, "RECORDS_DIR", folder)
    return folder
