"""Phase math on FAKE data."""

from datetime import date, timedelta

import pytest

from src import phase_engine
from src.database import add_body_metric
from src.database_v2 import add_meal, add_meal_item
from tests.conftest import TODAY, day


def test_cut_plan_numbers():
    plan = phase_engine.compute_plan("cut", body_weight=200, maintenance=2800, weekly_rate_pct=-0.75, target_weight=185)
    # 1.5 lb/week = 750 kcal/day deficit
    assert plan["weekly_change_lb"] == -1.5
    assert plan["calorie_target"] == 2050
    assert plan["protein_g"] == 185          # 1.0 g/lb of goal weight
    assert plan["fat_g"] >= 60               # >= 0.3 g/lb
    assert plan["protein_g"] * 4 + plan["fat_g"] * 9 + plan["carbs_g"] * 4 == pytest.approx(2050, abs=40)
    assert plan["weeks_to_target"] == 10.0
    assert plan["warnings"] == []


def test_bulk_and_out_of_range_warning():
    assert phase_engine.compute_plan("bulk", 180, 2700)["calorie_target"] == 2920  # +0.25%/wk = +225 kcal
    plan = phase_engine.compute_plan("bulk", 180, 2700, weekly_rate_pct=1.5)
    assert any("outside the usual" in w for w in plan["warnings"])


def test_wrong_direction_target_warns():
    plan = phase_engine.compute_plan("cut", 200, 2800, target_weight=210)
    assert any("other direction" in w for w in plan["warnings"])


def seed_month(today, start_weight=200.0, lb_per_week=-1.0, kcal=2300):
    for i in range(28):
        d = (today - timedelta(days=27 - i)).isoformat()
        meal = add_meal(d, "dinner")
        add_meal_item(meal, "fake food", 1, calories=kcal, protein_g=180)
        if i % 2 == 0:
            add_body_metric(d, round(start_weight + lb_per_week / 7 * i, 1))


def test_maintenance_from_logs():
    seed_month(TODAY)
    bal = phase_engine.energy_balance(TODAY)
    assert bal["maintenance_method"] == "your logs" and bal["confidence"] == "high"
    assert bal["weekly_change_lb"] == pytest.approx(-1.0, abs=0.05)
    # 2300 intake + 500/day deficit implied by -1 lb/week
    assert bal["maintenance_kcal"] == pytest.approx(2800, abs=20)


def test_formula_fallback_needs_profile():
    add_body_metric(day(0), 180.0)
    assert phase_engine.energy_balance(TODAY)["maintenance_kcal"] is None
    phase_engine.save_profile(sex="male", birth_year=1996, height_in=70, experience="intermediate")
    bal = phase_engine.energy_balance(TODAY)
    assert bal["maintenance_method"].startswith("formula") and bal["confidence"] == "low"
    assert 2500 <= bal["maintenance_kcal"] <= 3000


def test_save_plan_sets_nutrition_targets_and_progress():
    seed_month(TODAY, lb_per_week=-2.5)
    plan = phase_engine.compute_plan("cut", 200, 2800, weekly_rate_pct=-0.75)
    saved = phase_engine.save_plan({**plan, "start_weight": 200}, today=TODAY - timedelta(days=14))
    assert saved["status"] == "active" and saved["phase"] == "cut"

    from src.database_v2 import get_nutrition_target_for
    assert get_nutrition_target_for(TODAY.isoformat())["calories"] == plan["calorie_target"]

    bal = phase_engine.energy_balance(TODAY)
    progress = phase_engine.plan_progress(saved, bal, [], TODAY)
    assert any("faster than ideal" in c["message"] for c in progress["checks"])

    # a new plan archives the old one
    phase_engine.save_plan({**phase_engine.compute_plan("maintain", 195, 2800)}, today=TODAY)
    assert phase_engine.get_active_plan()["phase"] == "maintain"


def test_sports_inferred_from_logs_until_chosen():
    from src import coach_engine
    from src.database_v2 import add_athletic_session
    from tests.conftest import add_session

    assert phase_engine.get_profile()["effective_sports"] == []
    assert "plays basketball" not in coach_engine.system_prompt()

    add_session(day(1), "Upper A", [("Bench Press", 150, 5, 7, 0)])
    add_athletic_session(day(2), "basketball", subtype="practice", duration_minutes=60, rpe=6)
    profile = phase_engine.get_profile()
    assert profile["sports"] is None and profile["effective_sports"] == ["lifting", "basketball"]
    assert "plays basketball" in coach_engine.system_prompt()

    phase_engine.save_profile(sports=["running", "lifting"])
    profile = phase_engine.get_profile()
    assert profile["sports"] == ["lifting", "running"] and profile["effective_sports"] == ["lifting", "running"]
    assert "plays basketball" not in coach_engine.system_prompt()
    assert "lifting, running" in coach_engine.system_prompt()
