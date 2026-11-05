"""Coach analysis on FAKE training data."""

from datetime import date
from types import SimpleNamespace

import pytest

from src import coach_engine, garmin_store
from src.database import add_recovery, add_run
from tests.conftest import TODAY, add_session, day


def seed_lifting_with_jump():
    # Three steady weeks (~5,000 lb each), then a much bigger week.
    for week in (3, 2, 1):
        add_session(day(7 * week + 2), "Upper A", [("Bench Press", 150, 5, 7, 0)] * 4 + [("Row", 100, 8, 7, 0)] * 3)
    add_session(day(1), "Upper A", [("Bench Press", 160, 5, 7, 0)] * 6 + [("Row", 110, 10, 7, 0)] * 5)


def test_volume_jump_is_flagged():
    seed_lifting_with_jump()
    windows = coach_engine.weekly_load(TODAY)
    flags = coach_engine.load_jump_flags(windows)
    lifting = [f for f in flags if f["metric"] == "lifting_volume_lb"]
    assert len(lifting) == 1
    assert lifting[0]["severity"] == "high" and lifting[0]["change_pct"] >= 30


def test_steady_week_not_flagged():
    for week in (3, 2, 1, 0):
        add_session(day(7 * week + 1), "Upper A", [("Bench Press", 150, 5, 7, 0)] * 4)
    assert coach_engine.load_jump_flags(coach_engine.weekly_load(TODAY)) == []


def test_running_mileage_jump_flagged():
    for week in (3, 2, 1):
        add_run(day(7 * week + 1), 10.0, 90, 9.0, 5, None)
    add_run(day(1), 16.0, 140, 8.75, 6, None)
    flags = coach_engine.load_jump_flags(coach_engine.weekly_load(TODAY))
    assert any(f["metric"] == "running_miles" and f["change_pct"] == 60 for f in flags)


def test_readiness_from_checkin_only_without_garmin():
    add_recovery(day(0), 5.0, 7, 3, 0, None)
    snap = coach_engine.recovery_snapshot(TODAY)
    assert snap["garmin_available"] is False
    assert snap["readiness"] == "HOLD"
    assert snap["flags"][0]["source"] == "check-in"


def test_stale_checkin_not_used():
    add_recovery(day(10), 4.0, 2, 9, 0, None)
    snap = coach_engine.recovery_snapshot(TODAY)
    assert snap["readiness"] == "UNKNOWN"
    assert any("10 days ago" in n for n in snap["notes"])


def seed_garmin(hrv_today, sleep_today_h=7.5):
    conn = garmin_store.connect()
    with conn:
        for i in range(8, 0, -1):
            conn.execute(
                "INSERT INTO daily_recovery (date, sleep_seconds, hrv_overnight_avg, resting_hr, updated_at) VALUES (?, ?, ?, ?, 'x')",
                (day(i), 7.5 * 3600, 60, 52),
            )
        conn.execute(
            "INSERT INTO daily_recovery (date, sleep_seconds, hrv_overnight_avg, resting_hr, updated_at) VALUES (?, ?, ?, ?, 'x')",
            (day(0), sleep_today_h * 3600, hrv_today, 52),
        )
    conn.close()


def test_garmin_hrv_drop_adds_hold_on_top_of_good_checkin():
    add_recovery(day(0), 8.0, 8, 2, 0, None)
    seed_garmin(hrv_today=48)
    snap = coach_engine.recovery_snapshot(TODAY)
    assert snap["readiness"] == "HOLD"
    assert [f["metric"] for f in snap["flags"]] == ["hrv"]


def test_garmin_alone_can_give_go():
    seed_garmin(hrv_today=61)
    assert coach_engine.recovery_snapshot(TODAY)["readiness"] == "GO"


def test_next_workout_rotates_and_respects_readiness():
    add_session(day(5), "Lower A", [("Back Squat", 225, 5, 7, 0)] * 3)
    add_session(day(2), "Upper A", [("Bench Press", 155, 5, 7, 0)] * 3)

    plan = coach_engine.next_workout(TODAY, readiness="GO")
    assert plan["session_name"] == "Lower A"  # done longest ago
    squat = plan["exercises"][0]
    assert squat["decision"] == "INCREASE" and squat["recommended_weight"] == 230

    held = coach_engine.next_workout(TODAY, readiness="HOLD")
    assert held["exercises"][0]["decision"] == "HOLD"
    assert held["exercises"][0]["recommended_weight"] == 225


def test_no_history_means_no_plan():
    assert coach_engine.next_workout(TODAY) is None


def test_pain_triggers_see_a_professional_note():
    add_session(day(1), "Upper A", [("Bench Press", 155, 5, 7, 5)])
    insights = coach_engine.build_insights(TODAY)
    assert insights["pain_reports"][0]["pain"] == 5
    assert "doctor or physical therapist" in insights["safety_notes"][0]


def test_insights_work_with_an_empty_log():
    insights = coach_engine.build_insights(TODAY)
    assert insights["readiness"] == "UNKNOWN"
    assert insights["next_workout"] is None
    assert insights["load_flags"] == []


def test_ask_coach_sends_system_prompt_and_data_to_local_model(monkeypatch):
    seed_lifting_with_jump()
    sent = {}

    def fake_chat(model, messages, **kwargs):
        sent.update(model=model, messages=messages)
        return SimpleNamespace(message=SimpleNamespace(content="  Nice work.  "))

    monkeypatch.setattr(coach_engine.local_llm, "chat", fake_chat)
    result = coach_engine.ask_coach("summary", "gpt-oss:20b", insights=coach_engine.build_insights(TODAY))

    assert result["text"] == "Nice work."
    system = sent["messages"][0]["content"]
    assert "general training guidance only" in system.lower()
    assert "doctor or physical therapist" in system
    assert sent["messages"][1]["content"].startswith("DATA")
    assert "Bench Press" in sent["messages"][1]["content"]


def test_chat_requires_question():
    with pytest.raises(ValueError):
        coach_engine.ask_coach("chat", "gpt-oss:20b", question="  ", insights={"today": "x"})


def test_progression_ignores_stale_checkin(monkeypatch):
    from src.analytics import get_progression_recommendation

    add_session(day(1, date.today()), "Upper A", [("Bench Press", 155, 5, 7, 0)] * 3)
    add_recovery(day(10, date.today()), 4.0, 2, 9, 0, None)  # old and terrible
    assert get_progression_recommendation("Bench Press")["decision"] == "INCREASE"

    add_recovery(day(0, date.today()), 4.0, 7, 3, 0, None)  # fresh and short on sleep
    assert get_progression_recommendation("Bench Press")["decision"] == "HOLD"


def test_recovery_status_marks_stale():
    from src.analytics import get_recovery_status

    add_recovery(day(5, date.today()), 4.0, 2, 9, 0, None)
    status = get_recovery_status()
    assert status["status"] == "stale" and status["flags"] == []


def test_training_intensity_per_lift_and_muscle():
    add_session(day(8), "Upper A", [("Bench Press", 150, 5, 7, 0)] * 3 + [("Barbell Row", 135, 8, None, 0)] * 3)
    add_session(day(1), "Upper A", [("Bench Press", 160, 5, 8, 0)] * 2 + [("Bench Press", 165, 3, 9, 0)])
    out = coach_engine.training_intensity(TODAY)
    bench = next(l for l in out["lifts"] if l["exercise"] == "Bench Press")
    assert bench["sessions"] == 2 and bench["sets_per_week"] == 1.5
    assert bench["avg_rpe"] == 7.7 and bench["hard_set_share_pct"] == 50
    assert bench["last_top_set"] == "160 x 5 @8"  # higher e1RM than 165x3
    assert bench["last_top_set_pct_of_best"] == 100
    groups = {m["muscle"]: m for m in out["muscle_groups"]}
    assert groups["chest"]["working_sets_per_week"] == 1.5  # all 6 bench sets are RPE >= 7
    assert groups["back"]["status"] == "low"


@pytest.mark.parametrize("name, group", [("Romanian Deadlift", "hamstrings"), ("Back Squat", "quads"),
                                          ("Incline Bench Press", "chest"), ("Lat Pulldown", "back"),
                                          ("Overhead Press", "shoulders"), ("Hammer Curl", "biceps")])
def test_muscle_groups(name, group):
    assert coach_engine.muscle_group(name) == group
