"""API checks for import save + phase plans, on FAKE data."""

from datetime import date, timedelta

from fastapi.testclient import TestClient

from backend.main import app
from src.database import add_body_metric

client = TestClient(app)
TODAY = date.today()


def good_day(offset=1):
    return {
        "date": (TODAY - timedelta(days=offset)).isoformat(),
        "meals": [{"meal_type": "lunch", "items": [{"food_name": "fake bowl", "quantity": 1, "calories": 700, "protein_g": 45}]}],
        "workouts": [{"name": "Push", "exercises": [{"exercise": "Bench Press", "weight": 155, "reps": 5, "sets": 3, "rpe": 8}]}],
        "body_weight": 200.0,
        "recovery": {"sleep_hours": 7, "energy": None, "soreness": None, "pain": None},
    }


def test_commit_validates_before_writing():
    bad = good_day()
    bad["workouts"][0]["exercises"][0]["reps"] = 0
    assert client.post("/api/import/commit", json={"days": [good_day(2), bad]}).status_code == 422
    assert client.get("/api/workouts/sessions").json() == []  # nothing partially saved

    future = good_day(-3)
    assert client.post("/api/import/commit", json={"days": [future]}).status_code == 422


def test_commit_then_undo():
    res = client.post("/api/import/commit", json={"days": [good_day(1), good_day(2)]}).json()
    assert res["workout_sessions"] == 2 and res["meals"] == 2
    assert len(client.get("/api/workouts/sessions").json()) == 2
    assert client.post(f"/api/import/batches/{res['batch_id']}/undo").json() == {"undone": True}
    assert client.get("/api/workouts/sessions").json() == []
    assert client.post(f"/api/import/batches/{res['batch_id']}/undo").status_code == 404


def test_plan_needs_weight_then_works_with_profile():
    assert client.post("/api/coach/plan/preview", json={"phase": "cut"}).status_code == 422
    add_body_metric(TODAY.isoformat(), 200.0)
    assert client.put("/api/coach/profile", json={"sex": "male", "birth_year": 1995, "height_in": 70, "experience": "intermediate"}).status_code == 200
    preview = client.post("/api/coach/plan/preview", json={"phase": "cut", "target_weight": 185}).json()
    assert preview["calorie_target"] < preview["maintenance_kcal"]
    saved = client.post("/api/coach/plan", json={"phase": "cut", "target_weight": 185}).json()
    assert saved["phase"] == "cut" and saved["status"] == "active"
    assert client.get("/api/coach/phase").json()["active_plan"]["id"] == saved["id"]
    assert client.delete("/api/coach/plan").json() == {"ended": True}


def test_rate_limits_enforced():
    assert client.post("/api/coach/plan/preview", json={"phase": "cut", "weekly_rate_pct": -3}).status_code == 422
