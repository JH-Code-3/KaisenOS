"""Demo mode seeds a full, made-up dataset (into the test's temp folder)."""

from src import coach_engine, demo_data, running_analytics, week_planner
from src.database_v2 import get_meals, get_workout_sessions
from tests.conftest import TODAY


def test_demo_seed_fills_every_page():
    demo_data.seed(TODAY)
    assert len(get_workout_sessions()) >= 15
    assert len(get_meals()) > 100
    load = running_analytics.summary(TODAY)["load"]
    assert load["acute_7d"] > 0 and load["acwr"] is not None
    insights = coach_engine.build_insights(TODAY)
    assert insights["phase"]["active_plan"]["phase"] == "cut"
    assert insights["recovery"]["garmin_available"]
    assert insights["next_workout"] is not None
    assert week_planner.get_week(TODAY)["total"] > 0
