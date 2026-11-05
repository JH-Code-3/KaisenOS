"""
Garmin -> your log, one activity at a time, only when you click "Add".

Reads watch activities from data/garmin_data.sqlite (read-only) and
writes the ones you choose into the workout log as Basketball & Running
sessions. Nothing here touches the network. Each watch activity can be
added once (tracked by its Garmin activity id).
"""

import sqlite3
from datetime import date, timedelta

import src.database_v2 as database_v2
from src import garmin_store
from src.running_analytics import pace

# Garmin activity type -> session type in your log.
RUNNING_TYPES = {"running", "treadmill_running", "trail_running", "track_running", "indoor_running", "virtual_run"}
CONDITIONING_TYPES = {
    "walking", "hiking", "cycling", "indoor_cycling", "road_biking", "mountain_biking", "gravel_cycling",
    "elliptical", "indoor_rowing", "rowing", "lap_swimming", "open_water_swimming", "stair_climbing",
    "hiit", "cardio", "indoor_cardio", "fitness_equipment", "jump_rope",
}
NOT_SUPPORTED = {"strength_training"}  # lifts belong on the Workouts page (set-by-set)

LABELS = {
    "basketball": "Basketball",
    "running": "Run",
    "treadmill_running": "Treadmill run",
    "trail_running": "Trail run",
    "walking": "Walk",
    "hiking": "Hike",
    "cycling": "Bike",
    "indoor_cycling": "Indoor bike",
    "strength_training": "Strength",
}


def session_type_for(garmin_type: str) -> str | None:
    if garmin_type in NOT_SUPPORTED:
        return None
    if garmin_type == "basketball":
        return "basketball"
    if garmin_type in RUNNING_TYPES:
        return "running"
    return "conditioning"


def _linked_and_skipped() -> tuple[set[int], set[int]]:
    conn = sqlite3.connect(database_v2.DB_PATH)
    linked = {r[0] for r in conn.execute("SELECT garmin_activity_id FROM athletic_sessions WHERE garmin_activity_id IS NOT NULL")}
    skipped = {r[0] for r in conn.execute("SELECT activity_id FROM garmin_skipped_activities")}
    conn.close()
    return linked, skipped


def pending(today: date | None = None, days: int = 30) -> dict:
    """Watch activities not yet in your log (and not skipped), newest first."""

    today = today or date.today()
    since = (today - timedelta(days=days - 1)).isoformat()
    linked, skipped = _linked_and_skipped()
    logged_by_day: dict[tuple[str, str], int] = {}
    for s in database_v2.get_athletic_sessions():
        if s.get("garmin_activity_id") is None:
            key = (s["session_date"], s["session_type"])
            logged_by_day[key] = logged_by_day.get(key, 0) + 1

    items, strength = [], 0
    for a in garmin_store.get_recent_activities(since):
        if a["activity_id"] is None or a["activity_id"] in linked or a["activity_id"] in skipped:
            continue
        maps_to = session_type_for(a["type"])
        if maps_to is None:
            strength += 1
            continue
        items.append(
            {
                **a,
                "label": LABELS.get(a["type"], a["type"].replace("_", " ").capitalize()),
                "maps_to": maps_to,
                "possible_duplicate": logged_by_day.get((a["date"], maps_to), 0) > 0,
            }
        )
    return {"activities": items, "strength_not_shown": strength, "window_days": days}


def add_to_log(activity_id: int, subtype: str | None = None, run_type: str | None = None,
               rpe: float | None = None, notes: str | None = None) -> int:
    """Copy one watch activity into the log. Raises ValueError with a readable message."""

    activity = next((a for a in garmin_store.get_recent_activities("0000-01-01") if a["activity_id"] == activity_id), None)
    if activity is None:
        raise LookupError("That Garmin activity isn't in your synced data.")
    session_type = session_type_for(activity["type"])
    if session_type is None:
        raise ValueError("Strength workouts from the watch can't be added here. Log lifts on the Workouts page.")
    linked, _ = _linked_and_skipped()
    if activity_id in linked:
        raise ValueError("This activity is already in your log.")

    minutes = activity["minutes"]
    miles = activity["miles"] if session_type in ("running", "conditioning") else None
    label = LABELS.get(activity["type"], activity["type"].replace("_", " "))
    watch = [f"From Garmin ({label.lower()})"]
    if activity.get("avg_hr"):
        watch.append(f"avg HR {activity['avg_hr']:g}")
    if activity.get("training_load"):
        watch.append(f"Garmin load {activity['training_load']:g}")
    note = ", ".join(watch) + (f". {notes.strip()}" if notes and notes.strip() else "")

    return database_v2.add_athletic_session(
        activity["date"],
        session_type,
        subtype=(subtype or "practice") if session_type == "basketball" else None,
        run_type=run_type if session_type == "running" else None,
        distance_miles=miles,
        duration_minutes=minutes,
        pace_per_mile=pace(miles, minutes) if session_type == "running" else None,
        rpe=rpe,
        notes=note,
        garmin_activity_id=activity_id,
    )


def skip(activity_id: int) -> None:
    conn = sqlite3.connect(database_v2.DB_PATH)
    with conn:
        conn.execute("INSERT OR IGNORE INTO garmin_skipped_activities (activity_id) VALUES (?)", (activity_id,))
    conn.close()
