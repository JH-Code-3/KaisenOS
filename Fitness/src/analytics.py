from src.database import (
    get_workouts,
    get_runs,
    get_body_metrics,
)

from src.database_v2 import get_workout_sessions


# ==================================================
# BASIC CALCULATIONS
# ==================================================

def calculate_e1rm(weight, reps):
    if weight is None or reps is None:
        return None

    if reps <= 0:
        return None

    if reps == 1:
        return round(float(weight), 1)

    estimated_max = weight * (1 + reps / 30)

    return round(estimated_max, 1)


def calculate_volume(weight, sets, reps):
    if (
        weight is None
        or sets is None
        or reps is None
    ):
        return None

    if sets <= 0 or reps <= 0:
        return None

    volume = weight * sets * reps

    return round(volume, 1)


def calculate_pace(
    distance_miles,
    duration_minutes,
):
    if (
        distance_miles is None
        or duration_minutes is None
    ):
        return None

    if distance_miles <= 0:
        return None

    if duration_minutes <= 0:
        return None

    pace = duration_minutes / distance_miles

    return round(pace, 2)


def format_pace(pace_minutes):
    if pace_minutes is None:
        return None

    minutes = int(pace_minutes)

    seconds = round(
        (pace_minutes - minutes) * 60
    )

    if seconds == 60:
        minutes += 1
        seconds = 0

    return f"{minutes}:{seconds:02d}"


# ==================================================
# LATEST RECORD ANALYSIS
# ==================================================

def get_exercise_analysis(exercise_name):
    """
    Most recent logged entry for an exercise, from either the legacy
    `workouts` table or per-set workout_sessions — whichever is newer.
    """

    history = get_exercise_history(exercise_name)

    if not history:
        return None

    return history[0]


# ==================================================
# LATEST RUN
# ==================================================

def get_latest_run_analysis():
    runs = get_runs()

    if not runs:
        return None

    latest_run = runs[0]

    (
        run_date,
        distance_miles,
        duration_minutes,
        stored_pace,
        rpe,
        notes,
    ) = latest_run

    calculated_pace = calculate_pace(
        distance_miles,
        duration_minutes,
    )

    return {
        "date": run_date,
        "distance_miles": distance_miles,
        "duration_minutes": duration_minutes,
        "stored_pace": stored_pace,
        "calculated_pace": calculated_pace,
        "formatted_pace": format_pace(
            calculated_pace
        ),
        "rpe": rpe,
        "notes": notes,
    }


def get_latest_body_weight():
    metrics = get_body_metrics()

    if not metrics:
        return None

    for metric in metrics:
        (
            metric_date,
            body_weight,
            body_fat,
            waist,
            notes,
        ) = metric

        if body_weight is not None:
            return {
                "date": metric_date,
                "body_weight": body_weight,
            }

    return None


# ==================================================
# EXERCISE HISTORY
# ==================================================

def get_exercise_history(exercise_name):
    workouts = get_workouts()

    history = []

    for workout in workouts:
        (
            workout_date,
            exercise,
            weight,
            sets,
            reps,
            rpe,
            pain,
            notes,
        ) = workout

        if exercise.lower() != exercise_name.lower():
            continue

        history.append(
            {
                "date": workout_date,
                "exercise": exercise,
                "weight": weight,
                "sets": sets,
                "reps": reps,
                "rpe": rpe,
                "pain": pain,
                "notes": notes,
                "source": "legacy",
                "e1rm": calculate_e1rm(
                    weight,
                    reps,
                ),
                "volume": calculate_volume(
                    weight,
                    sets,
                    reps,
                ),
            }
        )

    history.extend(_per_set_exercise_entries(exercise_name))

    # Newest first. On the same date, per-set entries come first
    # because they are the more detailed record.
    history.sort(key=lambda entry: (entry["date"], entry.get("source") == "sets"), reverse=True)

    return history


def _per_set_exercise_entries(exercise_name):
    """
    Collapse each per-set workout session into one history entry for
    `exercise_name`, shaped like a legacy `workouts` row so trend and
    progression logic can use both sources unchanged.

    - weight/reps: the top set (highest e1RM; heaviest weight if no reps)
    - rpe/pain: the HIGHEST across completed sets, so progression
      decisions stay conservative
    - volume/e1rm: computed from every completed set
    """

    entries = []

    for session in get_workout_sessions():
        sets = [
            s for s in session.get("sets", [])
            if s.get("is_completed", 1)
            and s["exercise_name"].lower() == exercise_name.lower()
        ]

        if not sets:
            continue

        def top_set_key(s):
            e1rm = calculate_e1rm(s.get("weight"), s.get("reps"))
            return (e1rm if e1rm is not None else -1, s.get("weight") or 0)

        top = max(sets, key=top_set_key)

        rpes = [s["rpe"] for s in sets if s.get("rpe") is not None]
        pains = [s["pain"] for s in sets if s.get("pain") is not None]

        volume = 0.0
        has_volume = False
        for s in sets:
            v = calculate_volume(s.get("weight"), 1, s.get("reps"))
            if v is not None:
                volume += v
                has_volume = True

        entries.append(
            {
                "date": session["session_date"],
                "exercise": sets[0]["exercise_name"],
                "weight": top.get("weight"),
                "sets": len(sets),
                "reps": top.get("reps"),
                "rpe": max(rpes) if rpes else None,
                "pain": max(pains) if pains else None,
                "notes": session.get("notes"),
                "e1rm": calculate_e1rm(top.get("weight"), top.get("reps")),
                "volume": round(volume, 1) if has_volume else None,
                "source": "sets",
                "session_id": session["id"],
            }
        )

    return entries


# ==================================================
# EXERCISE TREND
# ==================================================

def get_exercise_trend(exercise_name):
    history = get_exercise_history(
        exercise_name
    )

    if len(history) < 2:
        return {
            "exercise": exercise_name,
            "status": "not_enough_data",
            "message":
                "At least two logged entries are required.",
        }

    latest = history[0]
    previous = history[1]

    latest_e1rm = latest["e1rm"]
    previous_e1rm = previous["e1rm"]

    if (
        latest_e1rm is None
        or previous_e1rm is None
    ):
        return {
            "exercise": exercise_name,
            "status": "insufficient_data",
        }

    change = round(
        latest_e1rm - previous_e1rm,
        1,
    )

    percent_change = round(
        (
            change
            / previous_e1rm
        ) * 100,
        1,
    )

    if change > 0:
        trend = "improving"

    elif change < 0:
        trend = "declining"

    else:
        trend = "stable"

    return {
        "exercise": exercise_name,
        "latest_date": latest["date"],
        "previous_date": previous["date"],
        "latest_e1rm": latest_e1rm,
        "previous_e1rm": previous_e1rm,
        "change_lb": change,
        "percent_change": percent_change,
        "trend": trend,
    }


# ==================================================
# BODY WEIGHT HISTORY
# ==================================================

def get_body_weight_history():
    metrics = get_body_metrics()

    history = []

    for metric in metrics:
        (
            metric_date,
            body_weight,
            body_fat,
            waist,
            notes,
        ) = metric

        if body_weight is None:
            continue

        history.append(
            {
                "date": metric_date,
                "body_weight": body_weight,
            }
        )

    return history


def get_body_weight_trend():
    history = get_body_weight_history()

    if len(history) < 2:
        return {
            "status": "not_enough_data",
            "message":
                "At least two body-weight entries are required.",
        }

    latest = history[0]
    previous = history[1]

    change = round(
        latest["body_weight"]
        - previous["body_weight"],
        1,
    )

    if change > 0:
        trend = "up"

    elif change < 0:
        trend = "down"

    else:
        trend = "stable"

    return {
        "latest_date": latest["date"],
        "previous_date": previous["date"],
        "latest_weight":
            latest["body_weight"],
        "previous_weight":
            previous["body_weight"],
        "change_lb": change,
        "trend": trend,
    }


def get_body_weight_summary():
    """
    Weight trend from 7-day averages (single weigh-ins swing a lot).
    The windows end on the most recent weigh-in, not today, so the
    numbers stay meaningful if logging lapses.
    """

    from datetime import date, timedelta

    history = get_body_weight_history()

    if not history:
        return None

    latest = history[0]
    end = date.fromisoformat(latest["date"])

    def window_average(first_day, last_day):
        values = [
            h["body_weight"]
            for h in history
            if first_day <= date.fromisoformat(h["date"]) <= last_day
        ]
        if not values:
            return None, 0
        return round(sum(values) / len(values), 1), len(values)

    avg_7d, entries_7d = window_average(end - timedelta(days=6), end)
    prev_avg_7d, prev_entries_7d = window_average(
        end - timedelta(days=13), end - timedelta(days=7)
    )

    weekly_change = (
        round(avg_7d - prev_avg_7d, 1)
        if avg_7d is not None and prev_avg_7d is not None
        else None
    )

    return {
        "latest_date": latest["date"],
        "latest_weight": latest["body_weight"],
        "avg_7d": avg_7d,
        "entries_7d": entries_7d,
        "prev_avg_7d": prev_avg_7d,
        "prev_entries_7d": prev_entries_7d,
        "weekly_change": weekly_change,
    }


# ==================================================
# RUNNING HISTORY
# ==================================================

def get_run_history():
    runs = get_runs()

    history = []

    for run in runs:
        (
            run_date,
            distance_miles,
            duration_minutes,
            stored_pace,
            rpe,
            notes,
        ) = run

        pace = calculate_pace(
            distance_miles,
            duration_minutes,
        )

        history.append(
            {
                "date": run_date,
                "distance_miles":
                    distance_miles,
                "duration_minutes":
                    duration_minutes,
                "pace_per_mile": pace,
                "formatted_pace":
                    format_pace(pace),
                "rpe": rpe,
                "notes": notes,
            }
        )

    return history


def get_run_trend():
    history = get_run_history()

    if len(history) < 2:
        return {
            "status": "not_enough_data",
            "message":
                "At least two runs are required.",
        }

    latest = history[0]
    previous = history[1]

    latest_pace = latest[
        "pace_per_mile"
    ]

    previous_pace = previous[
        "pace_per_mile"
    ]

    if (
        latest_pace is None
        or previous_pace is None
    ):
        return {
            "status": "insufficient_data",
        }

    change = round(
        latest_pace
        - previous_pace,
        2,
    )

    if change < 0:
        trend = "faster"

    elif change > 0:
        trend = "slower"

    else:
        trend = "stable"

    return {
        "latest_date": latest["date"],
        "previous_date": previous["date"],
        "latest_pace":
            format_pace(latest_pace),
        "previous_pace":
            format_pace(previous_pace),
        "pace_change_minutes":
            change,
        "trend": trend,
    }


# ==================================================
# TESTS
# ==================================================
# Recovery thresholds shared by progression decisions and the
# Recovery page, so both always agree.
RECOVERY_PAIN_REDUCE_AT = 4    # pain >= this -> REDUCE
RECOVERY_MIN_SLEEP_HOURS = 6   # sleep below this -> HOLD
RECOVERY_LOW_ENERGY_AT = 4     # energy <= this -> HOLD
RECOVERY_HIGH_SORENESS_AT = 7  # soreness >= this -> HOLD
RECOVERY_FRESH_DAYS = 2        # check-ins older than this don't affect today's call


def get_recovery_flags(sleep_hours, energy, soreness, pain):
    """
    Return the recovery measurements that should limit progression.
    severity "reduce" = back off load; "hold" = don't add load.
    """

    flags = []

    if pain is not None and pain >= RECOVERY_PAIN_REDUCE_AT:
        flags.append({"metric": "pain", "value": pain, "severity": "reduce",
                      "message": f"pain was {pain}/10"})

    if sleep_hours is not None and sleep_hours < RECOVERY_MIN_SLEEP_HOURS:
        flags.append({"metric": "sleep_hours", "value": sleep_hours, "severity": "hold",
                      "message": f"sleep was only {sleep_hours} hours"})

    if energy is not None and energy <= RECOVERY_LOW_ENERGY_AT:
        flags.append({"metric": "energy", "value": energy, "severity": "hold",
                      "message": f"energy was {energy}/10"})

    if soreness is not None and soreness >= RECOVERY_HIGH_SORENESS_AT:
        flags.append({"metric": "soreness", "value": soreness, "severity": "hold",
                      "message": f"soreness was {soreness}/10"})

    return flags


def get_recovery_status():
    """Latest recovery entry and what it means for training today."""

    from datetime import date
    from src.database_v2 import get_recovery_entries

    entries = get_recovery_entries(limit=1)

    if not entries:
        return {"status": "no_data", "latest": None, "flags": [], "days_old": None}

    latest = entries[0]
    flags = get_recovery_flags(
        latest["sleep_hours"], latest["energy"], latest["soreness"], latest["pain"]
    )

    if any(f["severity"] == "reduce" for f in flags):
        status = "reduce"
    elif flags:
        status = "hold"
    else:
        status = "ok"

    days_old = (date.today() - date.fromisoformat(latest["recovery_date"])).days

    if days_old > RECOVERY_FRESH_DAYS:
        # Too old to affect today's training call.
        status, flags = "stale", []

    return {"status": status, "latest": latest, "flags": flags, "days_old": days_old}


def get_progression_recommendation(exercise_name):
    """
    Recommend whether to INCREASE, HOLD, or REDUCE an exercise
    based on the latest workout and recent recovery data.

    This function uses deterministic rules rather than allowing
    the language model to make the progression decision.
    """

    workout = get_exercise_analysis(exercise_name)

    if not workout:
        return {
            "exercise": exercise_name,
            "decision": "NO DATA",
            "reason": "No workout data found for this exercise.",
        }

    rpe = workout.get("rpe")
    pain = workout.get("pain")
    weight = workout.get("weight")

    # ----------------------------------------------
    # GET LATEST RECOVERY DATA
    # ----------------------------------------------

    from src.database import get_recovery

    recovery_records = get_recovery()

    latest_recovery = None

    if recovery_records:
        latest_recovery = recovery_records[0]

    sleep_hours = None
    energy = None
    soreness = None
    recovery_pain = None

    # Only a recent check-in counts; an old one says nothing about today.
    if latest_recovery:
        from datetime import date

        age_days = (date.today() - date.fromisoformat(latest_recovery[0])).days

        if age_days <= RECOVERY_FRESH_DAYS:
            (
                recovery_date,
                sleep_hours,
                energy,
                soreness,
                recovery_pain,
                recovery_notes,
            ) = latest_recovery

    # ----------------------------------------------
    # SAFETY FIRST — PAIN
    # ----------------------------------------------

    if pain is not None and pain >= 4:
        return {
            "exercise": exercise_name,
            "decision": "REDUCE",
            "current_weight": weight,
            "reason": (
                f"Workout pain was {pain}/10. "
                "Do not increase load while pain is elevated."
            ),
        }

    recovery_flags = get_recovery_flags(
        sleep_hours, energy, soreness, recovery_pain
    )

    if any(f["severity"] == "reduce" for f in recovery_flags):
        return {
            "exercise": exercise_name,
            "decision": "REDUCE",
            "current_weight": weight,
            "reason": (
                f"Latest recovery pain was {recovery_pain}/10."
            ),
        }

    # ----------------------------------------------
    # POOR RECOVERY
    # ----------------------------------------------

    recovery_reasons = [f["message"] for f in recovery_flags]
    poor_recovery = bool(recovery_reasons)

    if poor_recovery:
        return {
            "exercise": exercise_name,
            "decision": "HOLD",
            "current_weight": weight,
            "reason": (
                "Recovery is currently limiting progression: "
                + ", ".join(recovery_reasons)
                + "."
            ),
        }

    # ----------------------------------------------
    # RPE-BASED PROGRESSION
    # ----------------------------------------------

    if rpe is None:
        return {
            "exercise": exercise_name,
            "decision": "HOLD",
            "current_weight": weight,
            "reason": (
                "No RPE was logged, so there is not enough "
                "information to safely increase the load."
            ),
        }

    if rpe <= 7:
        decision = "INCREASE"
        reason = (
            f"Latest working-set RPE was {rpe}, "
            "pain is acceptable, and recovery does not "
            "show a major limiting factor."
        )

    elif rpe <= 8:
        decision = "INCREASE"
        reason = (
            f"Latest working-set RPE was {rpe}. "
            "The load was challenging but still within "
            "the progression range."
        )

    elif rpe <= 9:
        decision = "HOLD"
        reason = (
            f"Latest working-set RPE was {rpe}. "
            "Repeat the load before increasing."
        )

    else:
        decision = "REDUCE"
        reason = (
            f"Latest working-set RPE was {rpe}. "
            "The load was at or near maximal effort."
        )

    return {
        "exercise": exercise_name,
        "decision": decision,
        "current_weight": weight,
        "rpe": rpe,
        "pain": pain,
        "sleep_hours": sleep_hours,
        "energy": energy,
        "soreness": soreness,
        "reason": reason,
    }


# ==================================================
# PER-SET ANALYTICS (workout_sessions / workout_sets)
# ==================================================
#
# The legacy `workouts` table stores one row per exercise with
# aggregate sets/reps. The newer workout_sessions/workout_sets tables
# (added in migrations.py) store one row per completed set, which is
# what the README asks for. These functions compute volume and e1RM
# from real per-set data instead of the aggregate shortcut.

def analyze_session_sets(session):
    """
    Given a session dict (as returned by database_v2.get_workout_sessions
    / get_workout_session, including its "sets" list), compute total
    volume load and best-set e1RM per exercise.

    Only completed sets count toward volume/e1RM. Planned-but-not-done
    sets (is_completed = 0) are excluded so a prescribed workout is
    never mistaken for a completed one.
    """

    exercises = {}

    for completed_set in session.get("sets", []):
        if not completed_set.get("is_completed", True):
            continue

        exercise_name = completed_set["exercise_name"]
        weight = completed_set.get("weight")
        reps = completed_set.get("reps")

        entry = exercises.setdefault(
            exercise_name,
            {"exercise": exercise_name, "total_volume": 0.0, "best_e1rm": None, "sets": 0},
        )

        entry["sets"] += 1

        set_volume = calculate_volume(weight, 1, reps)

        if set_volume is not None:
            entry["total_volume"] = round(entry["total_volume"] + set_volume, 1)

        set_e1rm = calculate_e1rm(weight, reps)

        if set_e1rm is not None:
            if entry["best_e1rm"] is None or set_e1rm > entry["best_e1rm"]:
                entry["best_e1rm"] = set_e1rm

    return {
        "session_id": session.get("id"),
        "session_date": session.get("session_date"),
        "exercises": list(exercises.values()),
    }


def get_weekly_training_volume(weeks_back=0):
    """
    Sum total set-level volume (weight x reps, completed sets only)
    across all logged sessions in the most recent 7-day window ending
    today, offset by `weeks_back` full weeks if requested.
    """

    from datetime import date, timedelta

    today = date.today()
    window_end = today - timedelta(days=7 * weeks_back)
    window_start = window_end - timedelta(days=6)

    sessions = get_workout_sessions()

    total_volume = 0.0
    session_count = 0

    for session in sessions:
        session_date_str = session.get("session_date")

        if not session_date_str:
            continue

        try:
            session_date = date.fromisoformat(session_date_str)
        except ValueError:
            continue

        if not (window_start <= session_date <= window_end):
            continue

        session_count += 1
        analysis = analyze_session_sets(session)

        for exercise in analysis["exercises"]:
            total_volume += exercise["total_volume"]

    return {
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "session_count": session_count,
        "total_volume": round(total_volume, 1),
    }


if __name__ == "__main__":

    print("BENCH ANALYSIS:")
    print(
        get_exercise_analysis(
            "Bench Press"
        )
    )

    print("\nBENCH HISTORY:")
    print(
        get_exercise_history(
            "Bench Press"
        )
    )

    print("\nBENCH TREND:")
    print(
        get_exercise_trend(
            "Bench Press"
        )
    )

    print("\nBODY WEIGHT TREND:")
    print(
        get_body_weight_trend()
    )

    print("\nRUN HISTORY:")
    print(
        get_run_history()
    )

    print("\nRUN TREND:")
    print(
        get_run_trend()
    )
    print("\nBENCH PROGRESSION:")
    print(get_progression_recommendation("Bench Press"))

    print("\nSQUAT PROGRESSION:")
    print(get_progression_recommendation("Back Squat"))