"""
Every test runs against a brand-new FAKE database in a temp folder.
The real data/athlete.db, data/garmin_data.sqlite, data/settings.json
and .env are never opened.
"""

import sys
from datetime import date, timedelta
from pathlib import Path

import os

import pytest

# The test client calls itself "testserver"; the Host check only accepts it when tests opt in.
os.environ["KAISEN_ALLOW_TEST_HOST"] = "1"

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import backend.config as config  # noqa: E402
import src.database as database  # noqa: E402
import src.database_v2 as database_v2  # noqa: E402
import src.garmin_store as garmin_store  # noqa: E402
import src.migrations as migrations  # noqa: E402


@pytest.fixture(autouse=True)
def fake_data_dir(tmp_path, monkeypatch):
    db = tmp_path / "athlete_fake.db"
    for module in (database, database_v2, migrations):
        monkeypatch.setattr(module, "DB_PATH", db)
    monkeypatch.setattr(garmin_store, "GARMIN_DB_PATH", tmp_path / "garmin_data_fake.sqlite")
    monkeypatch.setattr(config, "SETTINGS_PATH", tmp_path / "settings_fake.json")
    # Excel exports go to the temp folder, not the real workouts/ folder.
    import src.excel_generator as excel_generator
    monkeypatch.setattr(excel_generator, "OUTPUT_DIR", tmp_path / "workouts")
    # Make sure nothing can reach a real Ollama/Garmin through env settings.
    monkeypatch.delenv("GARMIN_PERSONAL_API_KEY", raising=False)
    database.create_database()
    return tmp_path


TODAY = date(2026, 6, 15)


def day(offset: int, today: date = TODAY) -> str:
    """ISO date `offset` days before `today`."""
    return (today - timedelta(days=offset)).isoformat()


def add_session(when: str, name: str, sets: list[tuple]) -> int:
    """sets: (exercise, weight, reps, rpe, pain)"""
    session_id = database_v2.add_workout_session(when, name=name)
    counts: dict[str, int] = {}
    for exercise, weight, reps, rpe, pain in sets:
        counts[exercise] = counts.get(exercise, 0) + 1
        database_v2.add_workout_set(
            session_id, exercise, counts[exercise], reps=reps, weight=weight, rpe=rpe, pain=pain
        )
    return session_id
