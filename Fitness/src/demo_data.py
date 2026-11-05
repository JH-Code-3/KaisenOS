"""
Synthetic demo data: six weeks of a made-up athlete who lifts, plays
basketball and runs. Used by `./start.sh --demo` (and for screenshots).

Everything here is invented. It is only ever written into the temporary
demo data folder, never into a real one.
"""

import json
import random
from datetime import date, timedelta

from src import database_v2 as db2
from src import garmin_store, phase_engine, week_planner
from src.database import add_body_metric, add_recovery, create_database

DAYS = 42


def _ago(today: date, n: int) -> str:
    return (today - timedelta(days=n)).isoformat()


def seed(today: date | None = None) -> None:
    today = today or date.today()
    rng = random.Random(7)  # same demo every time
    create_database()

    phase_engine.save_profile(sex="male", birth_year=2001, height_in=74, experience="intermediate",
                              sports=["lifting", "basketball", "running"])
    week_planner.save_availability([
        {"weekday": i, "status": s}
        for i, s in enumerate(["open", "practice", "open", "practice", "open", "game", "open"])
    ])

    # ---- Lifting: three rotating sessions, slow progression ----
    sessions = [
        ("Lower A", [("Back Squat", 225, 5, 3), ("Romanian Deadlift", 185, 8, 3), ("Walking Lunge", 50, 10, 2)]),
        ("Upper A", [("Bench Press", 165, 5, 3), ("Barbell Row", 145, 8, 3), ("Pull-up", None, 8, 3)]),
        ("Upper B", [("Overhead Press", 105, 6, 3), ("Incline Dumbbell Press", 55, 10, 3), ("Lat Pulldown", 130, 10, 3)]),
    ]
    lift_days = [d for d in range(DAYS, 0, -1) if (today - timedelta(days=d)).weekday() in (0, 2, 4)]
    for i, d in enumerate(lift_days):
        name, exercises = sessions[i % 3]
        sid = db2.add_workout_session(_ago(today, d), name=name)
        week = (DAYS - d) // 7
        for exercise, base, reps, sets in exercises:
            weight = None if base is None else base + 5 * week
            for n in range(1, sets + 1):
                rpe = min(9.5, 6.5 + 0.5 * n + rng.choice([0, 0, 0.5]))
                db2.add_workout_set(sid, exercise, n, reps=reps, weight=weight, rpe=rpe, pain=0)

    # ---- Basketball + runs ----
    for d in range(DAYS, 0, -1):
        weekday = (today - timedelta(days=d)).weekday()
        if weekday in (1, 3):
            db2.add_athletic_session(_ago(today, d), "basketball", subtype="practice",
                                     duration_minutes=rng.choice([75, 90, 90, 105]), rpe=rng.choice([6, 7, 7, 8]))
        elif weekday == 5:
            db2.add_athletic_session(_ago(today, d), "basketball", subtype="game", duration_minutes=rng.choice([60, 75]),
                                     rpe=rng.choice([8, 9]))
        elif weekday == 6 and d % 2:
            miles = round(rng.uniform(2.5, 4.5), 1)
            minutes = round(miles * rng.uniform(8.6, 9.6), 1)
            db2.add_athletic_session(_ago(today, d), "running", run_type="easy", distance_miles=miles,
                                     duration_minutes=minutes, pace_per_mile=round(minutes / miles, 2), rpe=4)
    db2.add_athletic_session(_ago(today, 3), "sprint", sprint_distance_yards=40, sprint_time_seconds=5.02, reps=6, rpe=8)

    # ---- Food: most days logged ----
    foods = {
        "breakfast": [("Eggs", 3, "egg", 210, 18, 2, 15), ("Oatmeal", 1, "cup", 300, 10, 54, 5), ("Banana", 1, None, 105, 1, 27, 0)],
        "lunch": [("Chicken rice bowl", 1, None, 750, 52, 85, 18), ("Turkey sandwich", 1, None, 520, 35, 48, 16)],
        "dinner": [("Salmon", 6, "oz", 350, 34, 0, 22), ("Steak", 8, "oz", 480, 56, 0, 26), ("Pasta with meat sauce", 1, "plate", 680, 32, 90, 18)],
        "snack": [("Greek yogurt", 1, "cup", 150, 20, 8, 4), ("Protein shake", 1, "scoop", 130, 25, 4, 2)],
    }
    for d in range(DAYS, 0, -1):
        if rng.random() < 0.15:
            continue
        for meal_type, options in foods.items():
            food = rng.choice(options)
            mid = db2.add_meal(_ago(today, d), meal_type)
            db2.add_meal_item(mid, food[0], food[1], serving_unit=food[2], calories=food[3],
                              protein_g=food[4], carbs_g=food[5], fat_g=food[6])

    # ---- Body weight (slow cut) and recovery check-ins ----
    for d in range(DAYS, -1, -1):
        if d % 2 == 0:
            weight = round(198 - (DAYS - d) * 0.09 + rng.uniform(-0.8, 0.8), 1)
            add_body_metric(_ago(today, d), weight, 16.5 if d == 0 else None, 33.5 if d == 0 else None, None)
        if d % 3 == 0:
            add_recovery(_ago(today, d), round(rng.uniform(6.5, 8.2), 1), rng.choice([6, 7, 8]), rng.choice([2, 3, 4]), 0, None)

    # ---- Phase plan + this week's plan ----
    balance = phase_engine.energy_balance(today)
    maintenance = balance["maintenance_kcal"] or 2900
    plan = phase_engine.compute_plan("cut", balance["latest_weight"] or 195, maintenance, -0.5, 188)
    phase_engine.save_plan({**plan, "start_weight": balance["latest_weight"], "target_weight": 188,
                            "training_days_per_week": 3, "priorities": "keep strength, bench 185"},
                           today=today - timedelta(days=21))
    week_planner.save_week(week_planner.build_week(today, training_days=[0, 2, 4], today=today))

    _seed_garmin(today, rng)


def _seed_garmin(today: date, rng: random.Random) -> None:
    """Fake 'synced' watch data so the Garmin panels have something to show."""
    conn = garmin_store.connect()
    run_id = garmin_store.start_run(conn, f"{today}T08:00:00", _ago(today, 13), today.isoformat())
    with conn:
        for d in range(30, -1, -1):
            conn.execute(
                """
                INSERT OR REPLACE INTO daily_recovery (date, sleep_seconds, sleep_score, hrv_overnight_avg, hrv_status,
                    resting_hr, body_battery_high, body_battery_low, stress_avg, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'demo')
                """,
                (_ago(today, d), int(rng.uniform(6.4, 8.3) * 3600), rng.randint(68, 88), rng.randint(58, 72), "BALANCED",
                 rng.randint(48, 54), rng.randint(70, 95), rng.randint(15, 35), rng.randint(20, 35)),
            )
    activities = [
        {"activityId": 900000 + d, "startTimeLocal": f"{_ago(today, d)} 18:00:00", "activityType": {"typeKey": "basketball"},
         "duration": 5400.0, "distance": 0.0, "averageHR": 140.0 + d, "activityTrainingLoad": 140.0}
        for d in (2, 4)
    ]
    garmin_store.save_raw(conn, "activities", _ago(today, 6), today.isoformat(), f"{today}T08:00:00", activities)
    garmin_store.finish_run(conn, run_id, f"{today}T08:00:30", "ok", 6, 0)
    conn.close()


if __name__ == "__main__":
    seed()
    print(json.dumps({"seeded": True}))
