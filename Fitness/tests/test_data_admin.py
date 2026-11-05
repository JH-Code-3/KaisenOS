"""Backup, restore, export, delete — on FAKE data in a temp folder."""

import io
import json
import os
import stat
import zipfile
from datetime import date

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from src import data_admin
from src.database_v2 import add_meal, add_meal_item, get_meals

client = TestClient(app, base_url="http://127.0.0.1:8000")
SAME_ORIGIN = {"Origin": "http://127.0.0.1:8000"}


def seed():
    m = add_meal(date.today().isoformat(), "lunch")
    add_meal_item(m, "fake bowl", 1, calories=700, protein_g=40)


def test_backup_restore_roundtrip_with_safety_copy():
    seed()
    first = client.post("/api/data/backups", headers=SAME_ORIGIN).json()
    assert first["reason"] == "manual"
    m = add_meal(date.today().isoformat(), "dinner")
    add_meal_item(m, "later food", 1, calories=500)
    assert len(get_meals()) == 2

    res = client.post(f"/api/data/backups/{first['name']}/restore", headers=SAME_ORIGIN).json()
    assert [x["meal_type"] for x in get_meals()] == ["lunch"]
    names = [b["name"] for b in client.get("/api/data/backups").json()]
    assert res["safety_backup"] in names  # the pre-restore copy has the dinner


@pytest.mark.parametrize("name", ["../../etc", "kaisen-20260101-000000-x/../../", "athlete.db", "kaisen-2026-bad"])
def test_restore_rejects_bad_names(name):
    r = client.post(f"/api/data/backups/{name}/restore", headers=SAME_ORIGIN)
    assert r.status_code in (404, 405, 422)  # never a restore


def test_restore_rejects_non_database(fake_data_dir):
    folder = fake_data_dir / "backups" / "kaisen-20260101-000000-manual"
    folder.mkdir(parents=True)
    (folder / "athlete.db").write_text("not a database")
    r = client.post("/api/data/backups/kaisen-20260101-000000-manual/restore", headers=SAME_ORIGIN)
    assert r.status_code == 422


def test_retention_keeps_newest_and_ignores_other_files(fake_data_dir, monkeypatch):
    (fake_data_dir / "backups").mkdir(exist_ok=True)
    (fake_data_dir / "backups" / "athlete_old_manual_copy.db").write_bytes(b"keep me")
    monkeypatch.setattr(data_admin, "KEEP_BACKUPS", 3)
    for _ in range(5):
        data_admin.create_backup("manual")
    assert len(data_admin.list_backups()) == 3
    assert (fake_data_dir / "backups" / "athlete_old_manual_copy.db").exists()


@pytest.mark.skipif(os.name != "posix", reason="POSIX permissions")
def test_backups_are_owner_only():
    seed()
    b = data_admin.create_backup("manual")
    folder = data_admin._backup_dir() / b["name"]
    assert stat.S_IMODE(os.stat(folder).st_mode) == 0o700
    assert stat.S_IMODE(os.stat(folder / "athlete.db").st_mode) == 0o600


def test_auto_backup_once_a_day():
    seed()
    assert data_admin.auto_backup_if_due()["reason"] == "auto"
    assert data_admin.auto_backup_if_due() is None


def test_exports_contain_all_tables():
    seed()
    j = client.get("/api/data/export.json").json()
    assert j["app"] == "KaisenOS" and j["training_log"]["meal_items"][0]["food_name"] == "fake bowl"
    r = client.get("/api/data/export.zip")
    assert r.headers["content-disposition"].startswith("attachment")
    names = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
    assert "training_log/meal_items.csv" in names and "training_log/workout_sets.csv" in names


def test_delete_requires_typed_confirmation_and_keeps_backups_unless_asked():
    seed()
    data_admin.create_backup("manual")
    assert client.post("/api/data/delete", json={"confirm": "yes"}, headers=SAME_ORIGIN).status_code == 422
    r = client.post("/api/data/delete", json={"confirm": "DELETE"}, headers=SAME_ORIGIN).json()
    assert data_admin._db().name in r["removed"] and r["backups_kept"]
    assert get_meals() == [] and len(data_admin.list_backups()) == 1   # fresh empty log, app still works
    client.post("/api/data/delete", json={"confirm": "DELETE", "include_backups": True}, headers=SAME_ORIGIN)
    assert data_admin.list_backups() == []


def test_delete_blocked_cross_site():
    r = client.post("/api/data/delete", json={"confirm": "DELETE"}, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
