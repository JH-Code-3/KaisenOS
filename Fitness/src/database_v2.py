"""
Data access for the additive tables created in migrations.py
(workout_sessions/workout_sets, athletic_sessions, meals/meal_items,
foods, goals, weekly_plans/weekly_plan_items).

Kept separate from database.py (the legacy flat tables coach.py still
uses) so neither file grows unmanageable. All writes use parameterized
queries and explicit transactions; nothing here touches the legacy
tables.
"""

import sqlite3

from .database import DB_PATH


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ==================================================
# WORKOUT SESSIONS + SETS
# ==================================================

def add_workout_session(session_date, session_time=None, name=None, notes=None):
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO workout_sessions (session_date, session_time, name, notes)
        VALUES (?, ?, ?, ?)
        """,
        (session_date, session_time, name, notes),
    )

    session_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return session_id


def add_workout_set(
    session_id,
    exercise_name,
    set_number,
    reps=None,
    weight=None,
    rpe=None,
    rest_seconds=None,
    pain=None,
    duration_seconds=None,
    is_completed=True,
    notes=None,
):
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO workout_sets (
            session_id, exercise_name, set_number, reps, weight,
            rpe, rest_seconds, pain, duration_seconds, is_completed, notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session_id,
            exercise_name,
            set_number,
            reps,
            weight,
            rpe,
            rest_seconds,
            pain,
            duration_seconds,
            1 if is_completed else 0,
            notes,
        ),
    )

    set_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return set_id


def get_workout_sessions(limit=None):
    conn = _connect()
    cursor = conn.cursor()

    query = "SELECT * FROM workout_sessions ORDER BY session_date DESC, id DESC"

    if limit is not None:
        query += f" LIMIT {int(limit)}"

    cursor.execute(query)
    sessions = [dict(row) for row in cursor.fetchall()]

    for session in sessions:
        cursor.execute(
            """
            SELECT * FROM workout_sets
            WHERE session_id = ?
            ORDER BY exercise_name, set_number
            """,
            (session["id"],),
        )
        session["sets"] = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return sessions


def get_workout_session(session_id):
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM workout_sessions WHERE id = ?", (session_id,))
    row = cursor.fetchone()

    if row is None:
        conn.close()
        return None

    session = dict(row)

    cursor.execute(
        """
        SELECT * FROM workout_sets
        WHERE session_id = ?
        ORDER BY exercise_name, set_number
        """,
        (session_id,),
    )
    session["sets"] = [dict(r) for r in cursor.fetchall()]

    conn.close()

    return session


def delete_workout_set(set_id):
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM workout_sets WHERE id = ?", (set_id,))
    conn.commit()
    deleted = cursor.rowcount
    conn.close()
    return deleted > 0



def delete_workout_session(session_id):
    """Delete a session and all of its sets in one transaction."""

    conn = _connect()

    try:
        with conn:
            conn.execute("DELETE FROM workout_sets WHERE session_id = ?", (session_id,))
            cursor = conn.execute("DELETE FROM workout_sessions WHERE id = ?", (session_id,))
            deleted = cursor.rowcount
    finally:
        conn.close()

    return deleted > 0


def get_exercise_names():
    """
    Every exercise name seen anywhere (exercise library, per-set logs,
    legacy workouts), de-duplicated case-insensitively, sorted A-Z.
    """

    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT name FROM exercises
        UNION SELECT exercise_name FROM workout_sets
        UNION SELECT exercise FROM workouts
        """
    )
    names = {}

    for (name,) in cursor.fetchall():
        if name and name.strip():
            names.setdefault(name.strip().lower(), name.strip())

    conn.close()

    return sorted(names.values(), key=str.lower)

# ==================================================
# ATHLETIC SESSIONS (running, sprinting, plyo, agility, conditioning)
# ==================================================

ATHLETIC_FIELDS = [
    "session_date", "session_type", "subtype", "run_type", "garmin_activity_id", "distance_miles", "duration_minutes", "pace_per_mile",
    "sprint_distance_yards", "sprint_time_seconds", "jump_height_inches", "reps", "rpe", "notes",
]


def add_athletic_session(session_date, session_type, **fields):
    values = {"session_date": session_date, "session_type": session_type, **fields}
    cols = [c for c in ATHLETIC_FIELDS if c in values]
    conn = _connect()
    with conn:
        session_id = conn.execute(
            f"INSERT INTO athletic_sessions ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
            [values[c] for c in cols],
        ).lastrowid
    conn.close()
    return session_id


def update_athletic_session(session_id, **fields):
    cols = [c for c in ATHLETIC_FIELDS if c in fields]
    conn = _connect()
    with conn:
        updated = conn.execute(
            f"UPDATE athletic_sessions SET {', '.join(f'{c} = ?' for c in cols)} WHERE id = ?",
            [fields[c] for c in cols] + [session_id],
        ).rowcount
    conn.close()
    return updated > 0


def delete_athletic_session(session_id):
    conn = _connect()
    with conn:
        deleted = conn.execute("DELETE FROM athletic_sessions WHERE id = ?", (session_id,)).rowcount
    conn.close()
    return deleted > 0


def get_athletic_sessions(limit=None):
    conn = _connect()
    cursor = conn.cursor()

    query = "SELECT * FROM athletic_sessions ORDER BY session_date DESC, id DESC"

    if limit is not None:
        query += f" LIMIT {int(limit)}"

    cursor.execute(query)
    sessions = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return sessions


def get_legacy_runs():
    """Read-only: runs coach.py wrote to the original `running` table (with ids)."""
    conn = _connect()
    rows = [dict(r) for r in conn.execute("SELECT * FROM running ORDER BY run_date DESC, id DESC")]
    conn.close()
    return rows


# ==================================================
# FOODS / MEALS / MEAL ITEMS
# ==================================================

def add_food(
    name,
    brand=None,
    serving_size=None,
    serving_unit=None,
    calories=None,
    protein_g=None,
    carbs_g=None,
    fat_g=None,
    fiber_g=None,
    source="manual",
    source_ref=None,
    retrieved_at=None,
    is_estimate=False,
):
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO foods (
            name, brand, serving_size, serving_unit, calories, protein_g,
            carbs_g, fat_g, fiber_g, source, source_ref, retrieved_at, is_estimate
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            brand,
            serving_size,
            serving_unit,
            calories,
            protein_g,
            carbs_g,
            fat_g,
            fiber_g,
            source,
            source_ref,
            retrieved_at,
            1 if is_estimate else 0,
        ),
    )

    food_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return food_id


def search_foods(query_text, limit=20):
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT * FROM foods
        WHERE name LIKE ? OR brand LIKE ?
        ORDER BY name
        LIMIT ?
        """,
        (f"%{query_text}%", f"%{query_text}%", limit),
    )

    foods = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return foods


def add_meal(meal_date, meal_type=None, notes=None):
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO meals (meal_date, meal_type, notes) VALUES (?, ?, ?)",
        (meal_date, meal_type, notes),
    )

    meal_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return meal_id


def add_meal_item(
    meal_id,
    food_name,
    quantity,
    serving_unit=None,
    calories=None,
    protein_g=None,
    carbs_g=None,
    fat_g=None,
    fiber_g=None,
    food_id=None,
    is_estimate=False,
):
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO meal_items (
            meal_id, food_id, food_name, quantity, serving_unit,
            calories, protein_g, carbs_g, fat_g, fiber_g, is_estimate
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            meal_id,
            food_id,
            food_name,
            quantity,
            serving_unit,
            calories,
            protein_g,
            carbs_g,
            fat_g,
            fiber_g,
            1 if is_estimate else 0,
        ),
    )

    item_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return item_id


def get_meals(meal_date=None, limit=None):
    conn = _connect()
    cursor = conn.cursor()

    query = "SELECT * FROM meals"
    params = ()

    if meal_date is not None:
        query += " WHERE meal_date = ?"
        params = (meal_date,)

    query += " ORDER BY meal_date DESC, id DESC"

    if limit is not None:
        query += f" LIMIT {int(limit)}"

    cursor.execute(query, params)
    meals = [dict(row) for row in cursor.fetchall()]

    for meal in meals:
        cursor.execute(
            "SELECT * FROM meal_items WHERE meal_id = ? ORDER BY id",
            (meal["id"],),
        )
        meal["items"] = [dict(r) for r in cursor.fetchall()]

    conn.close()

    return meals


def get_daily_nutrition_totals(nutrition_date):
    """
    Sum calories/macros for a given date across the new meal_items
    table AND the legacy `nutrition` table, so totals stay accurate
    no matter which logging path (coach.py or the new UI) was used.
    """

    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            COALESCE(SUM(mi.calories), 0) AS calories,
            COALESCE(SUM(mi.protein_g), 0) AS protein_g,
            COALESCE(SUM(mi.carbs_g), 0) AS carbs_g,
            COALESCE(SUM(mi.fat_g), 0) AS fat_g,
            COALESCE(SUM(mi.fiber_g), 0) AS fiber_g
        FROM meal_items mi
        JOIN meals m ON m.id = mi.meal_id
        WHERE m.meal_date = ?
        """,
        (nutrition_date,),
    )
    meal_totals = dict(cursor.fetchone())

    cursor.execute(
        """
        SELECT
            COALESCE(SUM(calories), 0) AS calories,
            COALESCE(SUM(protein_g), 0) AS protein_g,
            COALESCE(SUM(carbs_g), 0) AS carbs_g,
            COALESCE(SUM(fat_g), 0) AS fat_g
        FROM nutrition
        WHERE nutrition_date = ?
        """,
        (nutrition_date,),
    )
    legacy_totals = dict(cursor.fetchone())

    conn.close()

    return {
        "date": nutrition_date,
        "calories": meal_totals["calories"] + legacy_totals["calories"],
        "protein_g": meal_totals["protein_g"] + legacy_totals["protein_g"],
        "carbs_g": meal_totals["carbs_g"] + legacy_totals["carbs_g"],
        "fat_g": meal_totals["fat_g"] + legacy_totals["fat_g"],
        "fiber_g": meal_totals["fiber_g"],
    }


def add_nutrition_target(effective_date, calories=None, protein_g=None, carbs_g=None, fat_g=None, notes=None):
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO nutrition_targets (effective_date, calories, protein_g, carbs_g, fat_g, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (effective_date, calories, protein_g, carbs_g, fat_g, notes),
    )

    target_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return target_id


def get_latest_nutrition_target():
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM nutrition_targets ORDER BY effective_date DESC, id DESC LIMIT 1"
    )
    row = cursor.fetchone()
    conn.close()

    return dict(row) if row else None



def get_nutrition_target_for(on_date):
    """The target in effect on `on_date` (latest effective_date <= it)."""

    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM nutrition_targets
        WHERE effective_date <= ?
        ORDER BY effective_date DESC, id DESC LIMIT 1
        """,
        (on_date,),
    )
    row = cursor.fetchone()
    conn.close()

    return dict(row) if row else None


def delete_meal(meal_id):
    """Delete a meal and all of its items in one transaction."""

    conn = _connect()

    try:
        with conn:
            conn.execute("DELETE FROM meal_items WHERE meal_id = ?", (meal_id,))
            cursor = conn.execute("DELETE FROM meals WHERE id = ?", (meal_id,))
            deleted = cursor.rowcount
    finally:
        conn.close()

    return deleted > 0


def find_food_by_name(name):
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM foods WHERE LOWER(name) = LOWER(?) ORDER BY id LIMIT 1",
        (name.strip(),),
    )
    row = cursor.fetchone()
    conn.close()

    return dict(row) if row else None


def get_legacy_nutrition_for_date(nutrition_date):
    """Read-only: rows coach.py wrote to the original flat `nutrition` table."""

    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM nutrition WHERE nutrition_date = ? ORDER BY id",
        (nutrition_date,),
    )
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    return rows


# ==================================================
# RECOVERY / BODY (legacy tables, read with ids + delete)
# ==================================================
#
# database.py's get_recovery()/get_body_metrics() return tuples without
# ids and coach.py depends on that shape, so the UI uses these instead.

def get_recovery_entries(limit=None):
    conn = _connect()
    query = "SELECT * FROM recovery ORDER BY recovery_date DESC, id DESC"
    if limit is not None:
        query += f" LIMIT {int(limit)}"
    rows = [dict(r) for r in conn.execute(query).fetchall()]
    conn.close()
    return rows


def delete_recovery_entry(entry_id):
    conn = _connect()
    with conn:
        deleted = conn.execute("DELETE FROM recovery WHERE id = ?", (entry_id,)).rowcount
    conn.close()
    return deleted > 0



def update_recovery_entry(entry_id, recovery_date, sleep_hours, energy, soreness, pain, notes):
    conn = _connect()
    with conn:
        updated = conn.execute(
            """
            UPDATE recovery
            SET recovery_date = ?, sleep_hours = ?, energy = ?, soreness = ?, pain = ?, notes = ?
            WHERE id = ?
            """,
            (recovery_date, sleep_hours, energy, soreness, pain, notes, entry_id),
        ).rowcount
    conn.close()
    return updated > 0

def get_body_entries(limit=None):
    conn = _connect()
    query = "SELECT * FROM body_metrics ORDER BY metric_date DESC, id DESC"
    if limit is not None:
        query += f" LIMIT {int(limit)}"
    rows = [dict(r) for r in conn.execute(query).fetchall()]
    conn.close()
    return rows


def delete_body_entry(entry_id):
    conn = _connect()
    with conn:
        deleted = conn.execute("DELETE FROM body_metrics WHERE id = ?", (entry_id,)).rowcount
    conn.close()
    return deleted > 0


def update_body_entry(entry_id, metric_date, body_weight, body_fat, waist, notes):
    conn = _connect()
    with conn:
        updated = conn.execute(
            """
            UPDATE body_metrics
            SET metric_date = ?, body_weight = ?, body_fat = ?, waist = ?, notes = ?
            WHERE id = ?
            """,
            (metric_date, body_weight, body_fat, waist, notes, entry_id),
        ).rowcount
    conn.close()
    return updated > 0



# ==================================================
# GOALS
# ==================================================

def add_goal(goal_type, description=None, target_value=None, target_date=None):
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO goals (goal_type, description, target_value, target_date)
        VALUES (?, ?, ?, ?)
        """,
        (goal_type, description, target_value, target_date),
    )

    goal_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return goal_id


def get_goals(status=None):
    conn = _connect()
    cursor = conn.cursor()

    query = "SELECT * FROM goals"
    params = ()

    if status is not None:
        query += " WHERE status = ?"
        params = (status,)

    query += " ORDER BY created_at DESC"

    cursor.execute(query, params)
    goals = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return goals


def update_goal_status(goal_id, status):
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute("UPDATE goals SET status = ? WHERE id = ?", (status, goal_id))
    conn.commit()
    updated = cursor.rowcount
    conn.close()
    return updated > 0


# ==================================================
# WEEKLY PLANS (persisted alongside the Excel export)
# ==================================================

def save_weekly_plan(week_number, start_date, end_date, items):
    """
    items: list of dicts with keys matching weekly_plan_items columns
    (item_date, category, exercise, prescribed_weight, sets, reps,
    rest, target_rpe, session_type, planned_work, target, notes).
    """

    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO weekly_plans (week_number, start_date, end_date)
        VALUES (?, ?, ?)
        """,
        (week_number, start_date, end_date),
    )

    plan_id = cursor.lastrowid

    for item in items:
        cursor.execute(
            """
            INSERT INTO weekly_plan_items (
                plan_id, item_date, category, exercise, prescribed_weight,
                sets, reps, rest, target_rpe, session_type, planned_work,
                target, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                plan_id,
                item.get("item_date"),
                item.get("category"),
                item.get("exercise"),
                item.get("prescribed_weight"),
                item.get("sets"),
                item.get("reps"),
                item.get("rest"),
                item.get("target_rpe"),
                item.get("session_type"),
                item.get("planned_work"),
                item.get("target"),
                item.get("notes"),
            ),
        )

    conn.commit()
    conn.close()

    return plan_id


def get_weekly_plans(limit=10):
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM weekly_plans ORDER BY start_date DESC LIMIT ?",
        (limit,),
    )
    plans = [dict(row) for row in cursor.fetchall()]

    for plan in plans:
        cursor.execute(
            "SELECT * FROM weekly_plan_items WHERE plan_id = ? ORDER BY item_date, id",
            (plan["id"],),
        )
        plan["items"] = [dict(r) for r in cursor.fetchall()]

    conn.close()

    return plans


def set_plan_item_completed(item_id, is_completed, notes=None):
    conn = _connect()
    cursor = conn.cursor()

    if notes is not None:
        cursor.execute(
            "UPDATE weekly_plan_items SET is_completed = ?, notes = ? WHERE id = ?",
            (1 if is_completed else 0, notes, item_id),
        )
    else:
        cursor.execute(
            "UPDATE weekly_plan_items SET is_completed = ? WHERE id = ?",
            (1 if is_completed else 0, item_id),
        )

    conn.commit()
    updated = cursor.rowcount
    conn.close()

    return updated > 0

