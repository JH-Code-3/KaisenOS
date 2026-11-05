"""Note import on FAKE notes, with the model's answers simulated (no Ollama needed)."""

import json
import time
from datetime import date
from types import SimpleNamespace

from src import note_import as ni
from src.database_v2 import add_food, add_workout_session, get_meals, get_workout_sessions

TODAY = date(2026, 11, 4)

FAKE_NOTES = """Oct 27
3 eggs, toast. push day bench 100kg 5x3
bw 91kg

10/28 rest, slept 6h
some line the model ignores entirely
"""

FAKE_ANSWERS = {
    "Oct 27": {
        "date": None,
        "meals": [{"meal_type": "breakfast", "items": [
            {"food": "eggs", "quantity": 3, "unit": "egg", "calories": None, "protein_g": None, "carbs_g": None, "fat_g": None, "source": "3 eggs"},
            {"food": "toast", "quantity": None, "unit": None, "calories": None, "protein_g": None, "carbs_g": None, "fat_g": None, "source": "toast"},
        ]}],
        "workouts": [
            {"name": "push day", "exercises": [{"exercise": "bench", "weight": 100, "unit": "kg", "reps": 3, "sets": 5, "rpe": None, "source": "bench 100kg 5x3"}]},
            {"name": "bench", "exercises": [{"exercise": "Bench Press", "weight": 100, "unit": "kg", "reps": 3, "sets": 1, "rpe": 9, "source": "bench 100kg"}]},
        ],
        "body_weight": 91, "body_weight_unit": "kg", "sleep_hours": None, "energy": None, "soreness": None, "pain": None,
        "other_notes": None,
    },
    "10/28": {
        "date": None, "meals": [], "workouts": [], "body_weight": None, "body_weight_unit": None,
        "sleep_hours": 6, "energy": None, "soreness": None, "pain": None, "other_notes": "rest day",
    },
}


def fake_chat(model, messages, format=None, **kwargs):
    text = messages[-1]["content"]
    if format is ni.ESTIMATE_SCHEMA:
        rows = [{"index": i, "calories": 80, "protein_g": 3, "carbs_g": 14, "fat_g": 1} for i, _ in enumerate(text.splitlines())]
        return SimpleNamespace(message=SimpleNamespace(content=json.dumps({"items": rows})))
    key = next(k for k in FAKE_ANSWERS if text.startswith(k))
    return SimpleNamespace(message=SimpleNamespace(content=json.dumps(FAKE_ANSWERS[key])))


def run(monkeypatch, notes=FAKE_NOTES):
    monkeypatch.setattr(ni.local_llm, "chat", fake_chat)
    monkeypatch.setattr(ni.local_llm, "check_model", lambda m: None)
    job = ni.start_parse_job(notes, "fake-model", today=TODAY)
    for _ in range(200):
        result = ni.get_job(job)
        if result["status"] != "running":
            return result
        time.sleep(0.02)
    raise AssertionError("job didn't finish")


def test_split_handles_formats():
    blocks = ni.split_into_days(FAKE_NOTES, TODAY)
    assert [b["date"] for b in blocks] == ["2026-10-27", "2026-10-28"]


def test_parse_normalizes_and_reports_unparsed(monkeypatch):
    add_food("Eggs", serving_size=1, serving_unit="egg", calories=70, protein_g=6, carbs_g=0.5, fat_g=5)
    job = run(monkeypatch)
    assert job["status"] == "done"
    d1, d2 = job["days"]

    # exercises merged into one session; alias + kg -> lb
    assert len(d1["workouts"]) == 1 and d1["workouts"][0]["name"] == "push day"
    bench = d1["workouts"][0]["exercises"][0]
    assert bench["exercise"] == "Bench Press" and bench["weight"] == 220.5 and bench["sets"] == 5
    assert d1["body_weight"] == 200.6

    eggs, toast = d1["meals"][0]["items"]
    assert eggs["macro_source"] == "my_foods" and eggs["calories"] == 210 and not eggs["is_estimate"]
    assert toast["macro_source"] == "estimate" and toast["is_estimate"] and toast["calories"] == 80

    assert d2["recovery"]["sleep_hours"] == 6
    assert d2["not_imported"] == ["some line the model ignores entirely"]


def test_existing_entries_default_off(monkeypatch):
    add_workout_session("2026-10-27", name="already logged")
    d1 = run(monkeypatch)["days"][0]
    assert d1["existing"]["workouts"] == 1
    assert d1["include_workouts"] is False and d1["include_meals"] is True


def test_commit_and_undo(monkeypatch):
    days = run(monkeypatch)["days"]
    result = ni.commit_days(days)
    assert result["days"] == 2 and result["meals"] == 1 and result["workout_sessions"] == 1
    assert result["recovery_entries"] == 1 and result["body_entries"] == 1

    sessions = get_workout_sessions()
    assert len(sessions[0]["sets"]) == 6  # 5 sets + 1 set
    assert get_meals("2026-10-27")[0]["items"][1]["is_estimate"] == 1

    assert ni.undo_batch(result["batch_id"]) is True
    assert get_workout_sessions() == [] and get_meals() == []
    assert ni.list_batches()[0]["undone_at"] is not None


def test_model_failure_is_reported(monkeypatch):
    monkeypatch.setattr(ni.local_llm, "check_model", lambda m: None)

    def broken(*a, **k):
        raise ni.local_llm.LocalLLMError("Can't reach Ollama")

    monkeypatch.setattr(ni.local_llm, "chat", broken)
    job = ni.start_parse_job(FAKE_NOTES, "fake-model", today=TODAY)
    for _ in range(100):
        if ni.get_job(job)["status"] != "running":
            break
        time.sleep(0.02)
    assert ni.get_job(job)["status"] == "failed"
    assert "Ollama" in ni.get_job(job)["error"]


QUICK_ANSWER = {
    "date": None,
    "meals": [{"meal_type": "lunch", "items": [
        {"food": "chicken burrito bowl", "quantity": 1, "unit": None, "calories": 800, "protein_g": 55, "carbs_g": None, "fat_g": None, "source": "burrito bowl ~800 cal"},
    ]}],
    "workouts": [{"name": None, "exercises": [
        {"exercise": "bench", "weight": 155, "unit": "lb", "reps": 5, "sets": 3, "rpe": 8, "source": "benched 155x5x3 @8"},
    ]}],
    "activities": [
        {"type": "basketball", "kind": "practice", "distance": None, "distance_unit": None, "minutes": 90, "rpe": 7, "source": "90 min practice, felt like a 7"},
        {"type": "running", "kind": "easy", "distance": 5, "distance_unit": "km", "minutes": 28, "rpe": None, "source": "easy 5k in 28 min"},
        {"type": "swimming", "kind": None, "distance": None, "distance_unit": None, "minutes": 20, "rpe": None, "source": "bogus type"},
    ],
    "body_weight": None, "body_weight_unit": None, "sleep_hours": None, "energy": None, "soreness": None, "pain": None,
    "other_notes": None,
}


def quick_chat(model, messages, format=None, **kwargs):
    return SimpleNamespace(message=SimpleNamespace(content=json.dumps(QUICK_ANSWER)))


def test_quick_log_defaults_to_today_and_reads_activities(monkeypatch):
    monkeypatch.setattr(ni.local_llm, "chat", quick_chat)
    day = ni.parse_quick("lunch burrito bowl ~800 cal, benched 155x5x3 @8, 90 min practice felt like a 7, easy 5k in 28 min",
                         "fake-model", today=TODAY)
    assert day["date"] == TODAY.isoformat() and not day["warnings"]
    assert day["workouts"][0]["exercises"][0]["exercise"] == "Bench Press"
    bball, run = day["activities"]  # the unknown "swimming" type is dropped
    assert bball == {"session_type": "basketball", "subtype": "practice", "run_type": None, "distance_miles": None,
                     "duration_minutes": 90, "rpe": 7, "source": "90 min practice, felt like a 7"}
    assert run["run_type"] == "easy" and run["distance_miles"] == 3.11 and run["subtype"] is None
    assert day["include_activities"] and day["include_meals"]


def test_quick_log_named_day(monkeypatch):
    monkeypatch.setattr(ni.local_llm, "chat", quick_chat)
    assert ni.parse_quick("Oct 30 - burrito bowl", "fake-model", today=TODAY)["date"] == "2026-10-30"


def test_activities_commit_and_undo(monkeypatch):
    monkeypatch.setattr(ni.local_llm, "chat", quick_chat)
    day = ni.parse_quick("whatever", "fake-model", today=TODAY)
    result = ni.commit_days([day], source="coach")
    assert result["activities"] == 2 and result["meals"] == 1 and result["workout_sessions"] == 1

    from src import running_analytics as ra
    sessions = ra.all_sessions()
    run = next(s for s in sessions if s["session_type"] == "running")
    assert run["pace_per_mile"] == round(28 / 3.11, 2)
    assert ni.list_batches()[0]["source"] == "coach"

    ni.undo_batch(result["batch_id"])
    assert ra.all_sessions() == []


def test_recovery_merges_with_existing_day_and_undo_restores():
    from src.database import add_recovery
    from src.database_v2 import get_recovery_entries

    add_recovery(TODAY.isoformat(), None, 7, 3, 0, None)  # morning check-in: energy, soreness, pain
    day = {"date": TODAY.isoformat(), "meals": [], "workouts": [], "activities": [], "body_weight": None,
           "recovery": {"sleep_hours": 7.5, "energy": None, "soreness": 5, "pain": None}, "notes": None}
    batch = ni.commit_days([day], source="coach")["batch_id"]
    latest = get_recovery_entries(limit=1)[0]
    assert (latest["sleep_hours"], latest["energy"], latest["soreness"], latest["pain"]) == (7.5, 7, 5, 0)
    ni.undo_batch(batch)
    latest = get_recovery_entries(limit=1)[0]
    assert (latest["sleep_hours"], latest["soreness"]) == (None, 3)
