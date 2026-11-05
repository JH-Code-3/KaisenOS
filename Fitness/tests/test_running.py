"""Running & athleticism on FAKE data."""

from datetime import date, timedelta

from fastapi.testclient import TestClient

from backend.main import app
from src import running_analytics as ra
from src.database import add_run
from src.database_v2 import add_athletic_session

client = TestClient(app)
TODAY = date(2026, 11, 4)  # a Wednesday


def ago(n, today=TODAY):
    return (today - timedelta(days=n)).isoformat()


def run(days_ago, miles, minutes, run_type=None, rpe=None):
    add_athletic_session(ago(days_ago), "running", run_type=run_type, distance_miles=miles,
                         duration_minutes=minutes, pace_per_mile=ra.pace(miles, minutes), rpe=rpe)


def test_pace_and_formatting():
    assert ra.pace(3.1, 27.9) == 9.0
    assert ra.format_pace(8.5) == "8:30"
    assert ra.format_duration(65.5) == "1:05:30"
    assert ra.pace(0, 30) is None


def test_weekly_mileage_uses_calendar_weeks():
    run(0, 3, 30)    # this week (Mon Nov 2 ..)
    run(2, 4, 40)    # Mon Nov 2, this week
    run(3, 5, 50)    # Sun Nov 1, last week
    add_run(ago(10), 2.0, 20, 10.0, 5, None)  # legacy run, Sun Oct 25 = two weeks ago
    weeks = ra.weekly_mileage(ra.all_sessions(), TODAY)
    assert weeks[-1] == {"week_start": "2026-11-02", "miles": 7.0, "runs": 2, "long_run": 4}
    assert weeks[-2]["miles"] == 5.0 and weeks[-3]["miles"] == 2.0


def test_intensity_split_80_20():
    run(1, 8, 80, "long")
    run(2, 4, 32, "tempo")
    run(3, 3, 30, rpe=4)       # untyped, easy by RPE
    split = ra.intensity_split(ra.all_sessions(), TODAY)
    assert split["miles"]["easy"] == 11 and split["miles"]["hard"] == 4
    assert split["easy_share_pct"] == 73 and split["status"] == "ok"
    run(4, 6, 45, "intervals")
    assert ra.intensity_split(ra.all_sessions(), TODAY)["status"] == "too_hard"


def test_personal_bests_and_5k_estimate():
    run(5, 3.0, 27.0)            # 9:00 pace
    run(10, 6.0, 57.0)           # longest
    add_athletic_session(ago(3), "sprint", sprint_distance_yards=40, sprint_time_seconds=5.1)
    add_athletic_session(ago(1), "sprint", sprint_distance_yards=40, sprint_time_seconds=4.95)
    add_athletic_session(ago(2), "plyometric", jump_height_inches=28.5, reps=20)
    bests = ra.personal_bests(ra.all_sessions())
    assert bests["fastest_pace"]["pace_label"] == "9:00"
    assert bests["longest_run"]["distance_miles"] == 6.0
    assert bests["sprints"] == [{"distance_yards": 40, "time_seconds": 4.95, "date": ago(1)}]
    assert bests["best_jump"]["inches"] == 28.5
    est = ra.five_k_estimate(ra.all_sessions(), TODAY)
    assert 27 < est["minutes"] < 29.5 and est["label"].count(":") == 1


def test_api_validation_crud_and_pace_calculated():
    bad = {"session_date": date.today().isoformat(), "session_type": "running"}
    assert client.post("/api/running/sessions", json=bad).status_code == 422
    assert client.post("/api/running/sessions", json={**bad, "session_type": "swimming", "distance_miles": 1}).status_code == 422
    assert client.post("/api/running/sessions", json={**bad, "run_type": "jog", "distance_miles": 1}).status_code == 422
    assert client.post("/api/running/sessions", json={**bad, "session_type": "sprint"}).status_code == 422

    sid = client.post("/api/running/sessions", json={**bad, "distance_miles": 4, "duration_minutes": 36, "run_type": "easy"}).json()["id"]
    row = client.get("/api/running/sessions").json()[0]
    assert row["pace_per_mile"] == 9.0 and row["run_type"] == "easy"

    assert client.put(f"/api/running/sessions/{sid}", json={**bad, "distance_miles": 5, "duration_minutes": 40}).json() == {"saved": True}
    assert client.get("/api/running/sessions").json()[0]["pace_per_mile"] == 8.0
    assert client.get("/api/running/summary").status_code == 200
    assert client.delete(f"/api/running/sessions/{sid}").json() == {"deleted": True}
    assert client.delete(f"/api/running/sessions/{sid}").status_code == 404
