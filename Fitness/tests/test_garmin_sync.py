"""Garmin sync against a FAKE Garmin server (httpx.MockTransport). No network."""

import base64
import json
from datetime import date

import httpx
import pytest

import garmin_sync
from src import garmin_store

FAKE_KEY = "fake-key-for-tests"


def fake_jwt(exp=4102444800):
    payload = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).decode().rstrip("=")
    return f"eyJhbGciOiJub25lIn0.{payload}.sig"


def fake_garmin(token_status=200, data_status=200, data_overrides=None):
    calls = []

    def handler(request: httpx.Request):
        calls.append(request)
        if request.url.path == garmin_sync.TOKEN_PATH:
            if token_status != 200:
                return httpx.Response(token_status, text="nope")
            return httpx.Response(200, text=fake_jwt())
        for path_part, status in (data_overrides or {}).items():
            if path_part in request.url.path:
                return httpx.Response(status, text="error")
        if data_status != 200:
            return httpx.Response(data_status, text="error")
        return httpx.Response(200, json=[{"calendarDate": request.url.params.get("startDate", "2026-06-01"), "value": 1}])

    return httpx.MockTransport(handler), calls


def test_sync_pulls_every_endpoint_and_stores_locally(fake_data_dir):
    transport, calls = fake_garmin()
    summary = garmin_sync.run_sync(14, api_key=FAKE_KEY, transport=transport, today=date(2026, 6, 15), log=lambda *_: None)

    assert summary["status"] == "ok"
    # 6 endpoints x 2 week-chunks
    assert summary["saved"] == 12

    # Only Garmin's API host is contacted, token first, then Bearer auth.
    assert {c.url.host for c in calls} == {garmin_sync.API_HOST}
    token_call = calls[0]
    assert token_call.method == "POST" and token_call.url.path == garmin_sync.TOKEN_PATH
    assert token_call.headers["Authorization"] == f"ApiKey {FAKE_KEY}"
    assert all(c.headers["Authorization"].startswith("Bearer ") for c in calls[1:])
    assert all(c.method == "GET" for c in calls[1:])  # pull-only

    # Nothing secret is written to disk.
    db_bytes = (fake_data_dir / "garmin_data_fake.sqlite").read_bytes()
    assert FAKE_KEY.encode() not in db_bytes
    assert fake_jwt().encode() not in db_bytes

    run = garmin_store.get_last_sync()
    assert run["status"] == "ok" and run["raw_responses"] == 12


def test_fresh_token_every_run(fake_data_dir):
    for _ in range(2):
        transport, calls = fake_garmin()
        garmin_sync.run_sync(3, api_key=FAKE_KEY, transport=transport, today=date(2026, 6, 15), log=lambda *_: None)
        assert calls[0].url.path == garmin_sync.TOKEN_PATH


@pytest.mark.parametrize("status", [401, 403])
def test_expired_or_invalid_key_message(fake_data_dir, status):
    transport, _ = fake_garmin(token_status=status)
    with pytest.raises(garmin_sync.SyncError) as err:
        garmin_sync.run_sync(3, api_key=FAKE_KEY, transport=transport, log=lambda *_: None)
    message = str(err.value)
    assert "expired" in message and "Create a new key" in message
    assert FAKE_KEY not in message
    assert garmin_store.get_last_sync()["status"] == "failed"


def test_revoked_token_mid_sync(fake_data_dir):
    transport, _ = fake_garmin(data_status=401)
    with pytest.raises(garmin_sync.SyncError, match="revoked"):
        garmin_sync.run_sync(3, api_key=FAKE_KEY, transport=transport, log=lambda *_: None)


def test_one_failing_endpoint_is_partial_not_fatal(fake_data_dir):
    transport, _ = fake_garmin(data_overrides={"/hrv-service/": 500})
    summary = garmin_sync.run_sync(7, api_key=FAKE_KEY, transport=transport, today=date(2026, 6, 15), log=lambda *_: None)
    assert summary["status"] == "partial"
    assert summary["failed"] == 1 and summary["saved"] == 5


def test_describe_shows_field_names_not_values(fake_data_dir):
    transport, _ = fake_garmin()
    garmin_sync.run_sync(3, api_key=FAKE_KEY, transport=transport, today=date(2026, 6, 15), log=lambda *_: None)
    conn = garmin_store.connect()
    shapes = garmin_store.describe_raw(conn)
    conn.close()
    assert shapes["sleep_summaries"] == ["[].calendarDate: str", "[].value: int"]
    assert "2026-06" not in json.dumps(shapes)


def test_field_map_fills_daily_recovery(fake_data_dir):
    conn = garmin_store.connect()
    garmin_store.save_raw(
        conn, "sleep_summaries", "2026-06-14", "2026-06-15", "now",
        {"items": [{"day": "2026-06-14", "sleep": {"secs": 25200}}, {"day": "2026-06-15", "sleep": {"secs": 19800}}]},
    )
    written = garmin_store.extract_daily_recovery(
        conn, "now", field_map={"sleep_summaries": {"date": "day", "sleep_seconds": "sleep.secs"}}
    )
    conn.close()
    assert written == 2
    rows = garmin_store.get_daily_recovery("2026-06-01")
    assert [r["sleep_seconds"] for r in rows] == [25200, 19800]


def test_date_chunks_cover_range_without_gaps():
    chunks = list(garmin_sync.date_chunks(date(2026, 6, 1), date(2026, 6, 15)))
    assert chunks == [("2026-06-01", "2026-06-07"), ("2026-06-08", "2026-06-14"), ("2026-06-15", "2026-06-15")]


def test_missing_key_is_a_clear_error(monkeypatch, tmp_path):
    # Point the .env search at an empty folder so the real .env is never loaded.
    monkeypatch.setattr(garmin_sync, "__file__", str(tmp_path / "sub" / "garmin_sync.py"))
    with pytest.raises(garmin_sync.SyncError, match="isn't set"):
        garmin_sync.load_api_key()


def test_recovery_page_reads_garmin_nights(fake_data_dir):
    from datetime import date as _date, timedelta as _td

    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    assert client.get("/api/recovery/garmin").json() == {"nights": [], "last_sync": None}

    conn = garmin_store.connect()
    with conn:
        conn.execute(
            "INSERT INTO daily_recovery (date, sleep_seconds, hrv_overnight_avg, resting_hr, updated_at) VALUES (?, ?, ?, ?, 'x')",
            ((_date.today() - _td(days=1)).isoformat(), 7 * 3600, 58, 50),
        )
    conn.close()
    nights = client.get("/api/recovery/garmin").json()["nights"]
    assert len(nights) == 1 and nights[0]["hrv_overnight_avg"] == 58


def test_real_garmin_shapes_map_to_recovery(fake_data_dir):
    """Fake values in the exact shapes reported by `--describe`."""
    conn = garmin_store.connect()
    garmin_store.save_raw(conn, "sleep_summaries", "2026-11-01", "2026-11-03", "now", [
        {"calendarDate": "2026-11-02", "sleepTimeSeconds": 25200, "sleepScores": {"overall": {"value": 81, "qualifierKey": "GOOD"}}},
        {"calendarDate": "2026-11-03", "sleepTimeSeconds": 0, "sleepScores": {}},  # no reading
    ])
    garmin_store.save_raw(conn, "hrv_summaries", "2026-11-01", "2026-11-03", "now", {
        "hrvSummaries": [{"calendarDate": "2026-11-02", "lastNightAvg": 61, "status": "BALANCED", "weeklyAvg": 59}],
        "userProfilePk": 1,
    })
    garmin_store.save_raw(conn, "daily_summaries", "2026-11-01", "2026-11-03", "now", {"data": [
        {"calendarDate": "2026-11-02", "heartRate": {"restingValue": 49}, "bodyBattery": {"maxValue": 88, "minValue": 21},
         "stress": {"avgLevel": 27}},
        {"calendarDate": "2026-11-03", "heartRate": {"restingValue": 0}, "bodyBattery": {"maxValue": 70, "minValue": 30},
         "stress": {"avgLevel": -1}},
    ]})
    garmin_store.save_raw(conn, "activities", "2026-11-01", "2026-11-03", "now", [
        {"activityId": 7, "startTimeLocal": "2026-11-02 18:05:00", "activityType": {"typeKey": "basketball"},
         "duration": 5400.0, "distance": 0.0, "averageHR": 141.0, "maxHR": 188.0, "activityTrainingLoad": 152.3,
         "aerobicTrainingEffect": 3.4, "ownerFullName": "SHOULD NOT BE READ"},
        {"activityId": 8, "startTimeLocal": "2026-11-03 07:00:00", "activityType": {"typeKey": "running"},
         "duration": 1680.0, "distance": 4828.0, "averageHR": 150.0},
    ])
    assert garmin_store.extract_daily_recovery(conn, "now") == 2
    conn.close()

    by_date = {r["date"]: r for r in garmin_store.get_daily_recovery("2026-11-01")}
    n2, n3 = by_date["2026-11-02"], by_date["2026-11-03"]
    assert (n2["sleep_seconds"], n2["sleep_score"], n2["hrv_overnight_avg"], n2["hrv_status"]) == (25200, 81, 61, "BALANCED")
    assert (n2["resting_hr"], n2["body_battery_high"], n2["body_battery_low"], n2["stress_avg"]) == (49, 88, 21, 27)
    # zero / negative "no reading" values are left empty, real ones kept
    assert n3["sleep_seconds"] is None and n3["resting_hr"] is None and n3["stress_avg"] is None
    assert n3["body_battery_high"] == 70

    acts = garmin_store.get_recent_activities("2026-11-01")
    assert [a["type"] for a in acts] == ["running", "basketball"]
    assert acts[1] == {"activity_id": 7, "date": "2026-11-02", "type": "basketball", "minutes": 90, "miles": None, "avg_hr": 141,
                       "max_hr": 188, "training_load": 152, "aerobic_effect": 3.4}
    assert acts[0]["miles"] == 3.0
    assert "SHOULD NOT BE READ" not in str(acts)


def test_remap_runs_offline(fake_data_dir, monkeypatch, capsys):
    import httpx

    def no_network(*a, **k):
        raise AssertionError("remap must not use the network")

    monkeypatch.setattr(httpx.Client, "send", no_network)
    assert garmin_sync.main(["--remap"]) == 0
    assert "mapped for 0 day(s)" in capsys.readouterr().out
