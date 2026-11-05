"""Basketball load + availability-aware planning, on FAKE data."""

from datetime import date, timedelta

from fastapi.testclient import TestClient

from backend.main import app
from src import running_analytics as ra, week_planner as wp
from src.database_v2 import add_athletic_session
from tests.conftest import add_session

client = TestClient(app)
TODAY = date.today()
NEXT_MONDAY = wp.monday_of(TODAY) + timedelta(days=7)


def ago(n):
    return (TODAY - timedelta(days=n)).isoformat()


def test_session_rpe_load_and_spike():
    for week in range(1, 4):  # 3 normal weeks: 2 x 60 min @ RPE 6 = 720/week
        for d in (1, 3):
            add_athletic_session(ago(7 * week + d), "basketball", subtype="practice", duration_minutes=60, rpe=6)
    for d in range(0, 6, 2):  # this week: 3 x 90 min @ RPE 8 = 2160
        add_athletic_session(ago(d), "basketball", subtype="game", duration_minutes=90, rpe=8)
    load = ra.load_summary(ra.all_sessions(), TODAY)
    assert load["acute_7d"] == 2160
    assert load["chronic_weekly_avg"] == round((2160 + 720 * 3) / 4)
    assert load["status"] == "spike" and load["acwr"] > 1.5
    assert ra.session_load({"rpe": 7, "duration_minutes": 90}) == 630


def test_basketball_api_requires_minutes_and_kind():
    base = {"session_date": TODAY.isoformat(), "session_type": "basketball", "rpe": 7}
    assert client.post("/api/running/sessions", json=base).status_code == 422
    assert client.post("/api/running/sessions", json={**base, "subtype": "scrimmage", "duration_minutes": 60}).status_code == 422
    ok = client.post("/api/running/sessions", json={**base, "subtype": "practice", "duration_minutes": 90, "run_type": "easy"})
    assert ok.status_code == 200
    row = client.get("/api/running/sessions").json()[0]
    assert row["subtype"] == "practice" and row["run_type"] is None


def seed():
    add_session(ago(9), "Upper A", [("Bench Press", 150, 5, 7, 0)] * 3)
    add_session(ago(7), "Lower A", [("Back Squat", 225, 5, 7, 0)] * 3)
    add_session(ago(5), "Upper B", [("Overhead Press", 95, 8, 7, 0)] * 3)
    for week in range(1, 5):
        for r in range(3):
            add_athletic_session(ago(7 * week + r * 2 - TODAY.weekday()), "running", run_type="easy",
                                 distance_miles=3.0, duration_minutes=28, rpe=4)


def test_planner_respects_availability():
    seed()
    # Mon open, Tue practice, Wed open, Thu busy, Fri open, Sat game, Sun open
    avail = ["open", "practice", "open", "busy", "open", "game", "open"]
    week = wp.build_week(NEXT_MONDAY, training_days=[0, 2, 3, 4, 5], availability=avail)
    days = week["days"]

    assert week["training_days"] == [0, 2, 4]                       # busy Thu and game Sat dropped
    assert any("busy or game" in n for n in week["notes"])
    assert days[1]["items"][0]["category"] == "basketball" and days[5]["items"][0]["session_type"] == "Game"
    assert not any(i["category"] == "strength" for i in days[5]["items"])

    # Friday is the day before the game: no leg session there, or it's light
    fri = [i for i in days[4]["items"] if i["category"] == "strength"]
    assert all(i["exercise"] != "Back Squat" or i["target_rpe"] == 6 for i in fri)

    # runs avoid basketball days, the busy day, and the day before the game
    run_days = {n for n, d in enumerate(days) for i in d["items"] if i["category"] == "running"}
    assert not (run_days & {1, 3, 4, 5})
    # 3 usual runs - 2 basketball days = 1 run
    assert len(run_days) == 1


def test_all_basketball_week_skips_runs():
    seed()
    avail = ["practice", "practice", "open", "practice", "game", "open", "open"]
    week = wp.build_week(NEXT_MONDAY, availability=avail)
    assert not any(i["category"] == "running" for d in week["days"] for i in d["items"])
    assert any("covers your conditioning" in n for n in week["notes"])


def test_usual_week_saved_and_used_by_default():
    usual = [{"weekday": i, "status": s} for i, s in enumerate(["open", "practice", "open", "practice", "open", "game", "busy"])]
    assert client.put("/api/planner/availability", json=usual).status_code == 200
    assert client.put("/api/planner/availability", json=usual[:3]).status_code == 422
    defaults = client.get("/api/planner/defaults").json()
    assert defaults["availability"][5] == "game"
    assert all(defaults["availability"][d] in ("open", "practice") for d in defaults["training_days"])

    week = client.post("/api/planner/generate", json={"week_start": NEXT_MONDAY.isoformat()}).json()
    assert week["days"][5]["status"] == "game" and week["days"][6]["focus"] == "Busy"


def test_logged_basketball_ticks_plan():
    monday = wp.monday_of(TODAY)
    avail = ["practice"] + ["open"] * 6
    wp.save_week(wp.build_week(monday, training_days=[], availability=avail))
    add_athletic_session(monday.isoformat(), "basketball", subtype="practice", duration_minutes=75, rpe=7)
    item = wp.get_week(monday)["days"][0]["items"][0]
    assert item["category"] == "basketball" and item["done"]
