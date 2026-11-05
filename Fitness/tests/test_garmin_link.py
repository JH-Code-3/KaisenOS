"""Garmin activity -> log, on FAKE data. No network."""

from datetime import date, timedelta

from fastapi.testclient import TestClient

from backend.main import app
from src import garmin_link, garmin_store, running_analytics
from src.database_v2 import add_athletic_session

client = TestClient(app)
TODAY = date.today()


def ago(n):
    return (TODAY - timedelta(days=n)).isoformat()


def seed_watch():
    conn = garmin_store.connect()
    garmin_store.save_raw(conn, "activities", ago(6), ago(0), "now", [
        {"activityId": 101, "startTimeLocal": f"{ago(1)} 18:00:00", "activityType": {"typeKey": "basketball"},
         "duration": 5400.0, "distance": 0.0, "averageHR": 142.0, "activityTrainingLoad": 150.0},
        {"activityId": 102, "startTimeLocal": f"{ago(2)} 07:00:00", "activityType": {"typeKey": "treadmill_running"},
         "duration": 1800.0, "distance": 4828.0, "averageHR": 151.0},
        {"activityId": 103, "startTimeLocal": f"{ago(3)} 17:00:00", "activityType": {"typeKey": "strength_training"},
         "duration": 3600.0},
        {"activityId": 104, "startTimeLocal": f"{ago(4)} 12:00:00", "activityType": {"typeKey": "walking"},
         "duration": 2400.0, "distance": 3218.0},
        {"activityId": 105, "startTimeLocal": f"{ago(60)} 12:00:00", "activityType": {"typeKey": "running"},
         "duration": 1500.0, "distance": 4000.0},
    ])
    conn.close()


def test_pending_lists_new_activities_and_flags_duplicates():
    seed_watch()
    add_athletic_session(ago(1), "basketball", subtype="practice", duration_minutes=90, rpe=7)  # logged by hand
    res = client.get("/api/running/garmin").json()
    ids = [a["activity_id"] for a in res["activities"]]
    assert ids == [101, 102, 104]           # newest first; strength and old ones left out
    assert res["strength_not_shown"] == 1
    by_id = {a["activity_id"]: a for a in res["activities"]}
    assert by_id[101]["maps_to"] == "basketball" and by_id[101]["possible_duplicate"] is True
    assert by_id[102]["maps_to"] == "running" and by_id[102]["label"] == "Treadmill run"
    assert by_id[104]["maps_to"] == "conditioning"


def test_add_copies_watch_numbers_once():
    seed_watch()
    r = client.post("/api/running/garmin/101", json={"subtype": "game", "rpe": 8})
    assert r.status_code == 200
    s = next(x for x in running_analytics.all_sessions() if x.get("garmin_activity_id") == 101)
    assert (s["session_date"], s["session_type"], s["subtype"], s["duration_minutes"], s["rpe"]) == (ago(1), "basketball", "game", 90, 8)
    assert "avg HR 142" in s["notes"] and running_analytics.session_load(s) == 720

    assert client.post("/api/running/garmin/101", json={}).status_code == 409   # only once
    assert 101 not in [a["activity_id"] for a in client.get("/api/running/garmin").json()["activities"]]

    client.post("/api/running/garmin/102", json={"run_type": "easy"})
    run = next(x for x in running_analytics.all_sessions() if x.get("garmin_activity_id") == 102)
    assert run["distance_miles"] == 3.0 and run["pace_per_mile"] == 10.0 and run["run_type"] == "easy"


def test_strength_unknown_and_skip():
    seed_watch()
    assert client.post("/api/running/garmin/103", json={}).status_code == 409
    assert client.post("/api/running/garmin/999", json={}).status_code == 404
    assert client.post("/api/running/garmin/104/skip").json() == {"skipped": True}
    assert 104 not in [a["activity_id"] for a in client.get("/api/running/garmin").json()["activities"]]


def test_deleting_logged_session_makes_it_available_again():
    seed_watch()
    sid = client.post("/api/running/garmin/102", json={}).json()["id"]
    client.delete(f"/api/running/sessions/{sid}")
    assert 102 in [a["activity_id"] for a in client.get("/api/running/garmin").json()["activities"]]


def test_no_garmin_data_is_fine():
    assert garmin_link.pending()["activities"] == []
