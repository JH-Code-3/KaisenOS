import sqlite3
from pathlib import Path


# Anchor to the project root (Fitness/) regardless of the caller's
# current working directory, so this module behaves the same whether
# it's run as the CLI coach, imported by a FastAPI backend, or tested
# directly.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
from .paths import DATA_DIR  # noqa: E402  (personal data lives outside the code; see paths.py)

DB_PATH = DATA_DIR / "athlete.db"


# --------------------------------------------------
# CREATE DATABASE + TABLES
# --------------------------------------------------

def create_database():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS workouts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        workout_date TEXT NOT NULL,
        exercise TEXT NOT NULL,
        weight REAL,
        sets INTEGER,
        reps INTEGER,
        rpe REAL,
        pain REAL,
        notes TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS body_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        metric_date TEXT NOT NULL,
        body_weight REAL,
        body_fat REAL,
        waist REAL,
        notes TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS recovery (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        recovery_date TEXT NOT NULL,
        sleep_hours REAL,
        energy REAL,
        soreness REAL,
        pain REAL,
        notes TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS running (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_date TEXT NOT NULL,
        distance_miles REAL,
        duration_minutes REAL,
        pace_per_mile REAL,
        rpe REAL,
        notes TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS nutrition (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nutrition_date TEXT NOT NULL,
        calories REAL,
        protein_g REAL,
        carbs_g REAL,
        fat_g REAL,
        notes TEXT
    )
    """)

    conn.commit()
    conn.close()

    # Lazy import to avoid a circular import (migrations.py imports
    # DB_PATH from this module). Additive-only: see migrations.py.
    from .migrations import run_migrations

    run_migrations()


# --------------------------------------------------
# WORKOUT WRITE
# --------------------------------------------------

def add_workout(
    workout_date,
    exercise,
    weight,
    sets,
    reps,
    rpe,
    pain,
    notes,
):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO workouts (
        workout_date,
        exercise,
        weight,
        sets,
        reps,
        rpe,
        pain,
        notes
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        workout_date,
        exercise,
        weight,
        sets,
        reps,
        rpe,
        pain,
        notes,
    ))

    conn.commit()
    conn.close()


# --------------------------------------------------
# BODY METRICS WRITE
# --------------------------------------------------

def add_body_metric(
    metric_date,
    body_weight=None,
    body_fat=None,
    waist=None,
    notes=None,
):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO body_metrics (
        metric_date,
        body_weight,
        body_fat,
        waist,
        notes
    )
    VALUES (?, ?, ?, ?, ?)
    """, (
        metric_date,
        body_weight,
        body_fat,
        waist,
        notes,
    ))

    conn.commit()
    conn.close()


# --------------------------------------------------
# RECOVERY WRITE
# --------------------------------------------------

def add_recovery(
    recovery_date,
    sleep_hours=None,
    energy=None,
    soreness=None,
    pain=None,
    notes=None,
):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO recovery (
        recovery_date,
        sleep_hours,
        energy,
        soreness,
        pain,
        notes
    )
    VALUES (?, ?, ?, ?, ?, ?)
    """, (
        recovery_date,
        sleep_hours,
        energy,
        soreness,
        pain,
        notes,
    ))

    conn.commit()
    conn.close()


# --------------------------------------------------
# RUNNING WRITE
# --------------------------------------------------

def add_run(
    run_date,
    distance_miles=None,
    duration_minutes=None,
    pace_per_mile=None,
    rpe=None,
    notes=None,
):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO running (
        run_date,
        distance_miles,
        duration_minutes,
        pace_per_mile,
        rpe,
        notes
    )
    VALUES (?, ?, ?, ?, ?, ?)
    """, (
        run_date,
        distance_miles,
        duration_minutes,
        pace_per_mile,
        rpe,
        notes,
    ))

    conn.commit()
    conn.close()


# --------------------------------------------------
# NUTRITION WRITE
# --------------------------------------------------

def add_nutrition(
    nutrition_date,
    calories=None,
    protein_g=None,
    carbs_g=None,
    fat_g=None,
    notes=None,
):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO nutrition (
        nutrition_date,
        calories,
        protein_g,
        carbs_g,
        fat_g,
        notes
    )
    VALUES (?, ?, ?, ?, ?, ?)
    """, (
        nutrition_date,
        calories,
        protein_g,
        carbs_g,
        fat_g,
        notes,
    ))

    conn.commit()
    conn.close()


# --------------------------------------------------
# WORKOUT READ
# --------------------------------------------------

def get_workouts():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        workout_date,
        exercise,
        weight,
        sets,
        reps,
        rpe,
        pain,
        notes
    FROM workouts
    ORDER BY workout_date DESC, id DESC
    """)

    workouts = cursor.fetchall()

    conn.close()

    return workouts


def get_last_exercise(exercise_name):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        workout_date,
        exercise,
        weight,
        sets,
        reps,
        rpe,
        pain,
        notes
    FROM workouts
    WHERE LOWER(exercise) = LOWER(?)
    ORDER BY workout_date DESC, id DESC
    LIMIT 1
    """, (exercise_name,))

    workout = cursor.fetchone()

    conn.close()

    return workout


# --------------------------------------------------
# BODY METRICS READ
# --------------------------------------------------

def get_body_metrics():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        metric_date,
        body_weight,
        body_fat,
        waist,
        notes
    FROM body_metrics
    ORDER BY metric_date DESC, id DESC
    """)

    metrics = cursor.fetchall()

    conn.close()

    return metrics


# --------------------------------------------------
# RECOVERY READ
# --------------------------------------------------

def get_recovery():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        recovery_date,
        sleep_hours,
        energy,
        soreness,
        pain,
        notes
    FROM recovery
    ORDER BY recovery_date DESC, id DESC
    """)

    recovery = cursor.fetchall()

    conn.close()

    return recovery


# --------------------------------------------------
# RUNNING READ
# --------------------------------------------------

def get_runs():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        run_date,
        distance_miles,
        duration_minutes,
        pace_per_mile,
        rpe,
        notes
    FROM running
    ORDER BY run_date DESC, id DESC
    """)

    runs = cursor.fetchall()

    conn.close()

    return runs


# --------------------------------------------------
# NUTRITION READ
# --------------------------------------------------

def get_nutrition():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        nutrition_date,
        calories,
        protein_g,
        carbs_g,
        fat_g,
        notes
    FROM nutrition
    ORDER BY nutrition_date DESC, id DESC
    """)

    nutrition = cursor.fetchall()

    conn.close()

    return nutrition


# --------------------------------------------------
# DIRECT TEST
# --------------------------------------------------

if __name__ == "__main__":
    create_database()

    print("WORKOUTS:")

    workouts = get_workouts()

    if workouts:
        for workout in workouts:
            print(workout)
    else:
        print("No workouts found.")

    print("\nBODY METRICS:")

    metrics = get_body_metrics()

    if metrics:
        for metric in metrics:
            print(metric)
    else:
        print("No body metrics found.")

    print("\nRECOVERY:")

    recovery = get_recovery()

    if recovery:
        for entry in recovery:
            print(entry)
    else:
        print("No recovery data found.")

    print("\nRUNNING:")

    runs = get_runs()

    if runs:
        for run in runs:
            print(run)
    else:
        print("No running data found.")

    print("\nNUTRITION:")

    nutrition = get_nutrition()

    if nutrition:
        for entry in nutrition:
            print(entry)
    else:
        print("No nutrition data found.")