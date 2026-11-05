"""
Additive schema migrations.

Rules (see Kaisen/README.md "Data model and migrations"):
- Never drop or alter the original flat tables (workouts, body_metrics,
  recovery, running, nutrition) that coach.py and existing athlete
  records depend on.
- Only ADD new tables here. Each statement is CREATE TABLE IF NOT EXISTS
  so this module is safe to re-run on every backend startup.
- Back up data/athlete.db before running this against real data
  (see data/backups/).

These new tables support the richer, per-set / per-food-item data
model the dashboard needs, without touching the legacy tables that
already hold real history. A later read path can union legacy rows
with new rows; nothing here deletes or migrates old rows automatically.
"""

import sqlite3

from .database import DB_PATH


def run_migrations():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # ----------------------------------------------------------------
    # STRENGTH: exercise library, sessions, individual sets
    # ----------------------------------------------------------------

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS exercises (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        muscle_group TEXT,
        equipment TEXT,
        is_bodyweight INTEGER DEFAULT 0,
        notes TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS workout_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_date TEXT NOT NULL,
        session_time TEXT,
        name TEXT,
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS workout_sets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL REFERENCES workout_sessions(id) ON DELETE CASCADE,
        exercise_name TEXT NOT NULL,
        set_number INTEGER NOT NULL,
        reps INTEGER,
        weight REAL,
        rpe REAL,
        rest_seconds INTEGER,
        pain REAL,
        duration_seconds REAL,
        is_completed INTEGER DEFAULT 1,
        notes TEXT
    )
    """)

    # ----------------------------------------------------------------
    # RUNNING / ATHLETIC PERFORMANCE (richer than the legacy `running`
    # table: sprints, plyometrics, agility, conditioning)
    # ----------------------------------------------------------------

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS athletic_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_date TEXT NOT NULL,
        session_type TEXT NOT NULL,
        distance_miles REAL,
        duration_minutes REAL,
        pace_per_mile REAL,
        sprint_distance_yards REAL,
        sprint_time_seconds REAL,
        jump_height_inches REAL,
        rpe REAL,
        notes TEXT
    )
    """)

    # ----------------------------------------------------------------
    # NUTRITION: foods catalog, meals, meal items, targets
    # ----------------------------------------------------------------

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS foods (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        brand TEXT,
        serving_size REAL,
        serving_unit TEXT,
        calories REAL,
        protein_g REAL,
        carbs_g REAL,
        fat_g REAL,
        fiber_g REAL,
        source TEXT DEFAULT 'manual',
        source_ref TEXT,
        retrieved_at TEXT,
        is_estimate INTEGER DEFAULT 0
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS meals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        meal_date TEXT NOT NULL,
        meal_type TEXT,
        notes TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS meal_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        meal_id INTEGER NOT NULL REFERENCES meals(id) ON DELETE CASCADE,
        food_id INTEGER REFERENCES foods(id),
        food_name TEXT NOT NULL,
        quantity REAL NOT NULL,
        serving_unit TEXT,
        calories REAL,
        protein_g REAL,
        carbs_g REAL,
        fat_g REAL,
        fiber_g REAL,
        is_estimate INTEGER DEFAULT 0
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS nutrition_targets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        effective_date TEXT NOT NULL,
        calories REAL,
        protein_g REAL,
        carbs_g REAL,
        fat_g REAL,
        notes TEXT
    )
    """)

    # ----------------------------------------------------------------
    # BODY COMPOSITION / GOALS
    # ----------------------------------------------------------------

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS progress_photos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        photo_date TEXT NOT NULL,
        file_path TEXT NOT NULL,
        notes TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        goal_type TEXT NOT NULL,
        description TEXT,
        target_value REAL,
        target_date TEXT,
        status TEXT DEFAULT 'active',
        created_at TEXT DEFAULT (datetime('now'))
    )
    """)

    # ----------------------------------------------------------------
    # WEEKLY PLANNING (persisted, in addition to the Excel export)
    # ----------------------------------------------------------------

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS weekly_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        week_number INTEGER,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now'))
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS weekly_plan_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_id INTEGER NOT NULL REFERENCES weekly_plans(id) ON DELETE CASCADE,
        item_date TEXT NOT NULL,
        category TEXT NOT NULL,
        exercise TEXT,
        prescribed_weight REAL,
        sets INTEGER,
        reps INTEGER,
        rest TEXT,
        target_rpe REAL,
        session_type TEXT,
        planned_work TEXT,
        target TEXT,
        is_completed INTEGER DEFAULT 0,
        notes TEXT
    )
    """)

    # ----------------------------------------------------------------
    # GARMIN IMPORT (offline-first; see README "Garmin integration")
    # ----------------------------------------------------------------

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS garmin_import_batches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        imported_at TEXT DEFAULT (datetime('now')),
        source_method TEXT NOT NULL,
        file_name TEXT,
        file_hash TEXT,
        notes TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS garmin_activities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id INTEGER NOT NULL REFERENCES garmin_import_batches(id),
        activity_uid TEXT UNIQUE,
        activity_type TEXT,
        start_time TEXT,
        timezone TEXT,
        duration_seconds REAL,
        distance_miles REAL,
        avg_heart_rate REAL,
        max_heart_rate REAL,
        calories REAL,
        raw_data_json TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS garmin_daily_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id INTEGER NOT NULL REFERENCES garmin_import_batches(id),
        metric_date TEXT NOT NULL UNIQUE,
        resting_heart_rate REAL,
        hrv REAL,
        sleep_duration_minutes REAL,
        sleep_score REAL,
        body_battery REAL,
        stress REAL,
        vo2_max REAL,
        training_readiness REAL,
        raw_data_json TEXT
    )
    """)

    # ----------------------------------------------------------------
    # AI COACH: optional local chat history + logged recommendations
    # ----------------------------------------------------------------

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ai_chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now'))
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ai_recommendations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT DEFAULT (datetime('now')),
        category TEXT NOT NULL,
        recommendation TEXT NOT NULL,
        based_on_json TEXT
    )
    """)

    # ----------------------------------------------------------------
    # PRIVACY: audit log of every outbound public-food-lookup request
    # ----------------------------------------------------------------

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS outbound_request_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        requested_at TEXT DEFAULT (datetime('now')),
        endpoint TEXT NOT NULL,
        query_sent TEXT NOT NULL,
        source TEXT NOT NULL,
        success INTEGER,
        notes TEXT
    )
    """)

    # ----------------------------------------------------------------
    # COACHING: athlete profile (one row) and phase plans (cut/bulk/...)
    # ----------------------------------------------------------------

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS athlete_profile (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        sex TEXT,                -- "male" | "female" | NULL
        birth_year INTEGER,
        height_in REAL,
        experience TEXT,         -- "beginner" | "intermediate" | "advanced"
        updated_at TEXT DEFAULT (datetime('now'))
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS coach_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT DEFAULT (datetime('now')),
        status TEXT NOT NULL DEFAULT 'active',   -- active | archived
        phase TEXT NOT NULL,                     -- cut | bulk | maintain | recomp
        start_date TEXT NOT NULL,
        start_weight REAL,
        target_weight REAL,
        target_date TEXT,
        weekly_rate_pct REAL,                    -- % body weight per week (+ gain / - loss)
        calorie_target REAL,
        protein_g REAL,
        carbs_g REAL,
        fat_g REAL,
        training_days_per_week INTEGER,
        priorities TEXT,
        notes TEXT
    )
    """)

    # ----------------------------------------------------------------
    # NOTE IMPORTS: one row per import, so a whole import can be undone
    # ----------------------------------------------------------------

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS import_batches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT DEFAULT (datetime('now')),
        days INTEGER,
        meals INTEGER,
        workout_sessions INTEGER,
        recovery_entries INTEGER,
        body_entries INTEGER,
        undone_at TEXT
    )
    """)

    for table in ("meals", "workout_sessions", "recovery", "body_metrics"):
        _add_column_if_missing(cursor, table, "import_batch_id", "INTEGER")
    _add_column_if_missing(cursor, "athletic_sessions", "import_batch_id", "INTEGER")
    _add_column_if_missing(cursor, "import_batches", "activities", "INTEGER")
    _add_column_if_missing(cursor, "import_batches", "source", "TEXT")

    # Garmin -> log: which watch activity a session came from (each only once),
    # and activities you chose to skip.
    _add_column_if_missing(cursor, "athletic_sessions", "garmin_activity_id", "INTEGER")
    _add_column_if_missing(cursor, "athlete_profile", "sports", "TEXT")  # JSON list
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_athletic_garmin_activity "
        "ON athletic_sessions (garmin_activity_id) WHERE garmin_activity_id IS NOT NULL"
    )
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS garmin_skipped_activities (
        activity_id INTEGER PRIMARY KEY,
        skipped_at TEXT DEFAULT (datetime('now'))
    )
    """)

    # Running & athleticism: run type (easy/tempo/...) and reps (sprints, jumps)
    _add_column_if_missing(cursor, "athletic_sessions", "run_type", "TEXT")
    _add_column_if_missing(cursor, "athletic_sessions", "reps", "INTEGER")

    # Weekly planner: per-day focus and planner notes
    _add_column_if_missing(cursor, "weekly_plans", "focus_json", "TEXT")
    _add_column_if_missing(cursor, "weekly_plans", "notes_json", "TEXT")

    # Basketball: practice / game / skills / pickup
    _add_column_if_missing(cursor, "athletic_sessions", "subtype", "TEXT")

    # Your usual week: which days are open for training, busy, or basketball
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS weekly_availability (
        weekday INTEGER PRIMARY KEY CHECK (weekday BETWEEN 0 AND 6),  -- 0 = Monday
        status TEXT NOT NULL DEFAULT 'open',   -- open | busy | practice | game
        note TEXT
    )
    """)

    conn.commit()
    conn.close()


def _add_column_if_missing(cursor, table, column, column_type):
    """Additive only: adds a nullable column if it isn't there yet."""
    existing = {row[1] for row in cursor.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")


if __name__ == "__main__":
    run_migrations()
    print(f"Migrations applied to {DB_PATH}")
