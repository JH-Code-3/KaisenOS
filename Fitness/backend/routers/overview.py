from datetime import date

from fastapi import APIRouter

from src.database import get_recovery
from src.database_v2 import get_workout_sessions
from src.analytics import (
    get_latest_body_weight,
    get_weekly_training_volume,
    analyze_session_sets,
)
from src.database_v2 import get_daily_nutrition_totals

router = APIRouter(prefix="/api/overview", tags=["overview"])


@router.get("")
def overview():
    """
    Single aggregate endpoint for the dashboard's at-a-glance cards.
    Every value is either an observed record or is explicitly labeled
    as a count/estimate (e.g. "logged" vs. missing) — never invented.
    """

    today = date.today().isoformat()

    todays_nutrition = get_daily_nutrition_totals(today)

    latest_weight = get_latest_body_weight()

    recovery_rows = get_recovery()
    latest_recovery = None

    if recovery_rows:
        r = recovery_rows[0]
        latest_recovery = {
            "recovery_date": r[0],
            "sleep_hours": r[1],
            "energy": r[2],
            "soreness": r[3],
            "pain": r[4],
        }

    sessions = get_workout_sessions(limit=1)
    recent_session = None

    if sessions:
        recent_session = sessions[0]
        recent_session["analysis"] = analyze_session_sets(recent_session)

    weekly_volume = get_weekly_training_volume()

    return {
        "date": today,
        "todays_nutrition": todays_nutrition,
        "latest_body_weight": latest_weight,
        "latest_recovery": latest_recovery,
        "recent_workout_session": recent_session,
        "weekly_training_volume": weekly_volume,
    }
