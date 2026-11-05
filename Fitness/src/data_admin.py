"""
Your data: backup, restore, export and delete.

Backups
- A backup is a folder in <data dir>/backups named
  kaisen-YYYYMMDD-HHMMSS-<reason> holding a consistent copy of the
  training log (and Garmin store and settings, if present), made with
  SQLite's online backup API so it's safe while the app is running.
- One is made automatically at startup if the newest is over a day old,
  and before every restore. The newest KEEP_BACKUPS are kept; older
  ones are deleted. Other files in the backups folder are never touched.
- Backups are NOT encrypted. They're owner-only (0600) like the rest of
  your data; use full-disk encryption (FileVault/BitLocker/LUKS) to
  protect them at rest.

Export: every table as JSON, or one CSV per table in a zip.
Delete: removes the app's databases, settings, exports and log
(optionally the backups too) and starts fresh.
"""

import csv
import io
import json
import os
import re
import shutil
import sqlite3
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

import src.database as database
from src import garmin_store

KEEP_BACKUPS = 10
AUTO_BACKUP_EVERY = timedelta(hours=24)
BACKUP_NAME = re.compile(r"^kaisen-\d{8}-\d{6}-[a-z-]{1,20}$")
REQUIRED_TABLES = {"workouts", "meals", "workout_sessions", "recovery"}


def _db() -> Path:
    return Path(database.DB_PATH)


def _garmin_db() -> Path:
    return Path(garmin_store.GARMIN_DB_PATH)


def _backup_dir() -> Path:
    return _db().parent / "backups"


def _settings() -> Path:
    return _db().parent / "settings.json"


def _sqlite_copy(source: Path, target: Path) -> None:
    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    dst = sqlite3.connect(target)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()


# --------------------------------------------------
# Backups
# --------------------------------------------------

def create_backup(reason: str = "manual") -> dict:
    reason = re.sub(r"[^a-z-]", "", reason.lower())[:16] or "manual"
    stamp = f"{datetime.now():%Y%m%d-%H%M%S}"
    folder = _backup_dir() / f"kaisen-{stamp}-{reason}"
    while folder.exists():  # two backups in the same second: add a letter
        reason = (reason + "x")[-20:]
        folder = _backup_dir() / f"kaisen-{stamp}-{reason}"
    folder.mkdir(parents=True)
    _privatize(folder)
    if _db().exists():
        _sqlite_copy(_db(), folder / "athlete.db")
    if _garmin_db().exists():
        _sqlite_copy(_garmin_db(), folder / "garmin_data.sqlite")
    if _settings().exists():
        shutil.copy2(_settings(), folder / "settings.json")
    for f in folder.iterdir():
        _privatize(f)
    _apply_retention()
    return _describe(folder)


def _privatize(path: Path) -> None:
    """Owner-only, like everything else in the data folder."""
    if os.name == "posix":
        os.chmod(path, 0o700 if path.is_dir() else 0o600)


def _describe(folder: Path) -> dict:
    parts = folder.name.split("-")
    created = datetime.strptime(f"{parts[1]}{parts[2]}", "%Y%m%d%H%M%S")
    size = sum(f.stat().st_size for f in folder.iterdir() if f.is_file())
    return {
        "name": folder.name,
        "created": created.isoformat(timespec="seconds"),
        "reason": "-".join(parts[3:]).strip("-"),
        "size_bytes": size,
        "has_garmin": (folder / "garmin_data.sqlite").exists(),
    }


def list_backups() -> list[dict]:
    if not _backup_dir().exists():
        return []
    folders = [f for f in _backup_dir().iterdir() if f.is_dir() and BACKUP_NAME.match(f.name)]
    # Newest first by when the backup was written (names can tie within one second).
    folders.sort(key=lambda f: f.stat().st_mtime_ns, reverse=True)
    return [_describe(f) for f in folders]


def _apply_retention() -> None:
    for old in list_backups()[KEEP_BACKUPS:]:
        shutil.rmtree(_backup_dir() / old["name"])


def auto_backup_if_due() -> dict | None:
    """At startup: back up if there's data and the newest backup is over a day old."""
    if not _db().exists():
        return None
    backups = list_backups()
    if backups and datetime.now() - datetime.fromisoformat(backups[0]["created"]) < AUTO_BACKUP_EVERY:
        return None
    return create_backup("auto")


def _backup_folder(name: str) -> Path:
    """A backup folder by name, guaranteed to be directly inside the backups folder."""
    if not BACKUP_NAME.fullmatch(name):
        raise ValueError("Not a valid backup name.")
    root = os.path.realpath(_backup_dir())
    full = os.path.realpath(os.path.join(root, name))
    # Containment check before any other filesystem access.
    if not full.startswith(root + os.sep) or os.path.dirname(full) != root:
        raise ValueError("Not a valid backup name.")
    if not os.path.isdir(full):
        raise LookupError("Backup not found.")
    return Path(full)


def _check_backup_db(path: Path) -> None:
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        ok = conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        conn.close()
    except sqlite3.DatabaseError as exc:
        raise ValueError("That backup isn't a readable KaisenOS database.") from exc
    if not ok or not REQUIRED_TABLES <= tables:
        raise ValueError("That backup isn't a valid KaisenOS database.")


def restore_backup(name: str) -> dict:
    """Replace current data with a backup. Your current data is backed up first."""
    folder = _backup_folder(name)
    backup_db = folder / "athlete.db"
    if not backup_db.exists():
        raise ValueError("That backup has no training log.")
    _check_backup_db(backup_db)

    safety = create_backup("pre-restore")
    _sqlite_copy(backup_db, _db())
    if (folder / "garmin_data.sqlite").exists():
        _sqlite_copy(folder / "garmin_data.sqlite", _garmin_db())
    if (folder / "settings.json").exists():
        shutil.copy2(folder / "settings.json", _settings())
    database.create_database()  # bring an older backup up to the current schema (additive only)
    return {"restored": name, "safety_backup": safety["name"]}


# --------------------------------------------------
# Export
# --------------------------------------------------

def _tables(conn) -> list[str]:
    return [
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]


def _dump(path: Path, prefix: str = "") -> dict[str, list[dict]]:
    if not path.exists():
        return {}
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    out = {f"{prefix}{t}": [dict(r) for r in conn.execute(f'SELECT * FROM "{t}"')] for t in _tables(conn)}
    conn.close()
    return out


def export_all() -> dict:
    return {
        "app": "KaisenOS",
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "training_log": _dump(_db()),
        "garmin": _dump(_garmin_db()),
    }


def export_json_bytes() -> bytes:
    return json.dumps(export_all(), indent=2, default=str).encode()


def export_csv_zip_bytes() -> bytes:
    data = export_all()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for group in ("training_log", "garmin"):
            for table, rows in data[group].items():
                text = io.StringIO()
                if rows:
                    writer = csv.DictWriter(text, fieldnames=list(rows[0].keys()))
                    writer.writeheader()
                    writer.writerows(rows)
                zf.writestr(f"{group}/{table}.csv", text.getvalue())
    return buffer.getvalue()


# --------------------------------------------------
# Summary + delete
# --------------------------------------------------

def summary() -> dict:
    counts = {}
    if _db().exists():
        conn = sqlite3.connect(f"file:{_db()}?mode=ro", uri=True)
        for t in ("meals", "workout_sessions", "workouts", "athletic_sessions", "running", "recovery", "body_metrics"):
            try:
                counts[t] = conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
            except sqlite3.OperationalError:
                counts[t] = 0
        conn.close()
    size = sum(f.stat().st_size for f in _db().parent.rglob("*") if f.is_file()) if _db().parent.exists() else 0
    return {
        "data_dir": str(_db().parent),
        "total_size_bytes": size,
        "counts": counts,
        "has_garmin": _garmin_db().exists(),
        "backups": len(list_backups()),
        "keep_backups": KEEP_BACKUPS,
    }


def delete_all_data(include_backups: bool) -> dict:
    """Delete the app's personal data and start with an empty log."""
    removed = []
    data_dir = _db().parent
    for path in (_db(), _garmin_db(), _settings(), data_dir / "garmin_sync.log"):
        for candidate in (path, Path(f"{path}-wal"), Path(f"{path}-shm"), Path(f"{path}-journal")):
            if candidate.exists():
                candidate.unlink()
                removed.append(candidate.name)
    exports = data_dir / "exports"
    if exports.exists():
        shutil.rmtree(exports)
        removed.append("exports/")
    if include_backups and _backup_dir().exists():
        shutil.rmtree(_backup_dir())
        removed.append("backups/")
    database.create_database()  # fresh, empty log so the app keeps working
    return {"removed": removed, "backups_kept": not include_backups}
