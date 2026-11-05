"""
Where KaisenOS keeps your data, and keeping it private.

Personal data (databases, settings, backups, exports, logs) lives in ONE
folder, outside the code so it can never be committed by accident:

  1. KAISEN_DATA_DIR, if you set it, or
  2. <project>/Fitness/data, if an existing install already keeps its
     database there (so older installs keep working unchanged), or
  3. the standard per-user app-data folder:
       macOS    ~/Library/Application Support/KaisenOS
       Linux    $XDG_DATA_HOME/KaisenOS  (default ~/.local/share/KaisenOS)
       Windows  %APPDATA%\\KaisenOS

The folder is owner-only (0700) and files in it owner-only (0600) on
macOS/Linux, so other accounts on the same computer can't read them.
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LEGACY_DATA_DIR = PROJECT_ROOT / "data"
APP_NAME = "KaisenOS"


def default_data_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    if sys.platform.startswith("win"):
        return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / APP_NAME
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / APP_NAME


def resolve_data_dir() -> Path:
    override = os.environ.get("KAISEN_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    if (LEGACY_DATA_DIR / "athlete.db").exists():
        return LEGACY_DATA_DIR
    return default_data_dir()


DATA_DIR = resolve_data_dir()
BACKUP_DIR = DATA_DIR / "backups"
EXPORT_DIR = DATA_DIR / "exports"


def make_private() -> None:
    """
    Create the data folders and make everything in them owner-only.
    New files are created owner-only too (umask 077 for this process).
    """

    if os.name == "posix":
        os.umask(0o077)
    for folder in (DATA_DIR, BACKUP_DIR, EXPORT_DIR):
        folder.mkdir(parents=True, exist_ok=True)
    if os.name != "posix":
        return  # Windows: per-user AppData is already private to the account
    for root, dirs, files in os.walk(DATA_DIR):
        os.chmod(root, 0o700)
        for name in files:
            path = os.path.join(root, name)
            if not os.path.islink(path):
                os.chmod(path, 0o600)
