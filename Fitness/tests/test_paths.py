"""Where personal data lives, and that it's private."""

import os
import stat
import sys

import pytest

from src import paths


def test_env_override_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("KAISEN_DATA_DIR", str(tmp_path / "mine"))
    assert paths.resolve_data_dir() == (tmp_path / "mine").resolve()


def test_new_install_uses_app_data_folder_outside_repo(monkeypatch, tmp_path):
    monkeypatch.delenv("KAISEN_DATA_DIR", raising=False)
    monkeypatch.setattr(paths, "LEGACY_DATA_DIR", tmp_path / "no-legacy-here")
    resolved = paths.resolve_data_dir()
    assert paths.PROJECT_ROOT not in resolved.parents and resolved != paths.PROJECT_ROOT
    if sys.platform == "darwin":
        assert resolved.parts[-3:] == ("Library", "Application Support", "KaisenOS")


def test_existing_install_keeps_legacy_folder(monkeypatch, tmp_path):
    monkeypatch.delenv("KAISEN_DATA_DIR", raising=False)
    legacy = tmp_path / "data"
    legacy.mkdir()
    (legacy / "athlete.db").write_bytes(b"")
    monkeypatch.setattr(paths, "LEGACY_DATA_DIR", legacy)
    assert paths.resolve_data_dir() == legacy


@pytest.mark.skipif(os.name != "posix", reason="POSIX permissions")
def test_make_private_locks_down_folder_and_files(monkeypatch, tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "athlete.db").write_bytes(b"x")
    os.chmod(data / "athlete.db", 0o644)
    monkeypatch.setattr(paths, "DATA_DIR", data)
    monkeypatch.setattr(paths, "BACKUP_DIR", data / "backups")
    monkeypatch.setattr(paths, "EXPORT_DIR", data / "exports")
    old = os.umask(0o022)
    try:
        paths.make_private()
        assert stat.S_IMODE(os.stat(data).st_mode) == 0o700
        assert stat.S_IMODE(os.stat(data / "athlete.db").st_mode) == 0o600
        assert stat.S_IMODE(os.stat(data / "backups").st_mode) == 0o700
        (data / "new.txt").write_text("x")  # created after: umask makes it private too
        assert stat.S_IMODE(os.stat(data / "new.txt").st_mode) == 0o600
    finally:
        os.umask(old)
