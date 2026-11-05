"""Weekly planner on FAKE data."""

from datetime import date, timedelta

from fastapi.testclient import TestClient
from openpyxl import load_workbook

from backend.main import app
from src import phase_engine, running_analytics, week_planner as wp
from src.database_v2 import add_athletic_session
from tests.conftest import add_session

client = TestClient(app)
TODAY = date.today()
NEXT_MONDAY = wp.monday_of(TODAY) + timedelta(days=7)


def ago(n):
    return (TODAY - timedelta(days=n)).isoformat()


def seed_lifting():
    add_session(ago(9), "Upper A", [("Bench Press", 150, 5, 7, 0)] * 3 + [("Barbell Row", 135, 8, 7, 0)] * 3)
    add_session(ago(7), "Lower A", [("Back Squat", 225, 5, 7, 0)] * 3 + [("Romanian Deadlift", 185, 8, 7, 0)] * 2)
    add_session(ago(5), "Upper A", [("Bench Press", 155, 5, 7, 0)] * 3 + [("Barbell Row", 135, 8, 7, 0)] * 3)


def seed_running(weekly_miles=12.0, runs=3):
    for week in range(1, 5):
        for r in range(runs):
            miles = round(weekly_miles / runs, 1)
            add_athletic_session(ago(7 * week + r * 2 - (TODAY.weekday())), "running", run_type="easy",
                                 distance_miles=miles, duration_minutes=miles * 9.5, rpe=4)


def test_rotation_uses_your_sessions_and_progression():
    seed_lifting()
    week = wp.build_week(NEXT_MONDAY, training_days=[0, 2, 4])
    lifts = [d for d in week["days"] if any(i["category"] == "strength" for i in d["items"])]
    assert [d["focus"] for d in lifts] == ["Lower A", "Upper A", "Lower A"]  # least recently done first
    squat = lifts[0]["items"][0]
    assert squat["exercise"] == "Back Squat" and squat["sets"] == 3 and squat["reps"] == 5
    assert squat["prescribed_weight"] == 230  # RPE 7 -> INCREASE by 5
    assert week["days"][1]["focus"].startswith(("Rest", "Easy", "Tempo", "Long"))


def test_starter_template_without_history():
    week = wp.build_week(NEXT_MONDAY)
    assert week["training_days"] == [0, 1, 3, 4]  # default 4 days
    assert week["days"][0]["focus"] == "Lower strength"
    assert all(i["prescribed_weight"] is None for d in week["days"] for i in d["items"])
    assert any("starter template" in n for n in week["notes"])


def test_running_plan_caps_increase_and_places_runs():
    seed_lifting()
    seed_running(weekly_miles=12, runs=3)
    week = wp.build_week(NEXT_MONDAY, training_days=[0, 2, 4])
    runs = [(i, it) for i, d in enumerate(week["days"]) for it in d["items"] if it["category"] == "running"]
    assert len(runs) == 3
    total = sum(float(it["planned_work"].split()[0]) for _, it in runs)
    assert total <= 12 * 1.1 + 0.3
    kinds = {it["session_type"]: i for i, it in runs}
    miles = {it["session_type"]: float(it["planned_work"].split()[0]) for _, it in runs}
    assert miles["Long"] >= miles["Easy"]
    assert kinds["Long"] in (5, 6)
    lower_days = {i for i, d in enumerate(week["days"]) if d["focus"] == "Lower A"}
    assert not ({kinds["Tempo"] - 1, kinds["Tempo"], kinds["Tempo"] + 1} & lower_days)


def test_cut_holds_mileage_flat():
    seed_running(weekly_miles=10, runs=2)
    phase_engine.save_plan(phase_engine.compute_plan("cut", 200, 2800) | {"training_days_per_week": 3})
    week = wp.build_week(NEXT_MONDAY)
    assert week["training_days"] == [0, 2, 4]
    total = sum(float(it["planned_work"].split()[0]) for d in week["days"] for it in d["items"] if it["category"] == "running")
    assert total <= 10.05
    assert any("held flat" in n for n in week["notes"])


def test_api_generate_save_complete_edit_export():
    seed_lifting()
    week = client.post("/api/planner/generate", json={"week_start": TODAY.isoformat(), "training_days": [0, 3]}).json()
    assert week["week_start"] == wp.monday_of(TODAY).isoformat() and week["total"] > 0

    # regenerating replaces, not duplicates
    again = client.post("/api/planner/generate", json={"week_start": TODAY.isoformat(), "training_days": [0, 3]}).json()
    assert again["total"] == week["total"]

    item = next(i for d in again["days"] for i in d["items"])
    assert client.patch(f"/api/planner/items/{item['id']}", json={"prescribed_weight": 999, "is_completed": True}).json() == {"updated": True}
    reloaded = client.get(f"/api/planner/week/{TODAY.isoformat()}").json()
    changed = next(i for d in reloaded["days"] for i in d["items"] if i["id"] == item["id"])
    assert changed["prescribed_weight"] == 999 and changed["done"]

    res = client.get(f"/api/planner/week/{TODAY.isoformat()}/excel")
    assert res.status_code == 200 and res.content[:2] == b"PK"

    assert client.delete(f"/api/planner/items/{item['id']}").json() == {"deleted": True}
    assert client.get(f"/api/planner/week/{(TODAY + timedelta(days=21)).isoformat()}").json() is None
    assert client.post("/api/planner/generate", json={"week_start": TODAY.isoformat(), "training_days": [9]}).status_code == 422


def test_auto_completion_from_logs():
    seed_lifting()
    monday = wp.monday_of(TODAY)
    wp.save_week(wp.build_week(monday, training_days=[monday.weekday()]))
    add_session(monday.isoformat(), "Lower A", [("Back Squat", 230, 5, 7, 0)])
    week = wp.get_week(monday)
    squat = next(i for i in week["days"][0]["items"] if i["exercise"] == "Back Squat")
    assert squat["auto_completed"] and squat["done"]
