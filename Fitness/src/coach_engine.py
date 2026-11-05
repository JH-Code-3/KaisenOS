"""
AI coach: deterministic analysis + a local LLM to explain it.

Every number, flag and recommendation is computed here in Python from
your local data. The model (Ollama on localhost, see local_llm.py) only
turns that into plain-language coaching — it never invents the numbers.

Data sources (all local files):
- Workout log, data/athlete.db: lifting sessions/sets, runs, recovery
  check-ins, nutrition, body measurements. This is the primary source.
- Garmin, data/garmin_data.sqlite: optional extra recovery detail
  (measured sleep, HRV, resting HR). The coach works fully without it.
"""

import json
from datetime import date, timedelta
from statistics import mean

from src import garmin_store, local_llm
from src.analytics import (
    RECOVERY_FRESH_DAYS,
    RECOVERY_PAIN_REDUCE_AT,
    RECOVERY_MIN_SLEEP_HOURS,
    analyze_session_sets,
    calculate_volume,
    get_body_weight_summary,
    get_exercise_trend,
    get_recovery_flags,
)
from src.database import get_runs, get_workouts
from src.database_v2 import (
    get_athletic_sessions,
    get_daily_nutrition_totals,
    get_nutrition_target_for,
    get_recovery_entries,
    get_workout_sessions,
)
from src.weekly_planner import get_next_weight
from src import phase_engine, running_analytics
from src.analytics import calculate_e1rm

# Week-over-week load jump thresholds (vs. the average of the 3 weeks before).
JUMP_CAUTION_PCT = 10
JUMP_HIGH_PCT = 30
# Garmin: HRV this far below your own 7-day baseline counts as a recovery flag.
HRV_DROP_PCT = 10
RESTING_HR_RISE_BPM = 5

def system_prompt() -> str:
    sports = phase_engine.get_profile()["effective_sports"]
    sport_line = (
        "\n- The athlete plays basketball. Keep heavy leg work away from the day before games."
        if "basketball" in sports else ""
    )
    trains = ", ".join(sports) if sports else "not specified yet"
    return SYSTEM_PROMPT.replace("{sport_line}", sport_line) + f"\n\nThe athlete's sports/training: {trains}."


SYSTEM_PROMPT = """You are a private, local strength-and-conditioning assistant for one athlete.

Rules you must follow:
- Give general training guidance only. You are not a doctor or physical therapist. Do not diagnose, and do not give medical, rehab, supplement-dosing or medication advice.
- If the athlete mentions pain, an injury, or symptoms such as sharp, worsening or radiating pain, numbness, swelling, dizziness or chest pain, tell them to stop the movement that causes it and to see a doctor or physical therapist. Don't suggest training through pain.
- Use the DATA block as the source of truth. Its numbers, flags and recommended loads were calculated by the app from the athlete's logs; do not change them or make up new numbers. If something isn't in the data, say it isn't logged.
- Garmin data is optional. When it is missing, rely on the athlete's own logs and check-ins without complaining about it.
- garmin_activities_14d is what the watch recorded (type, minutes, avg HR, Garmin training load). It can
  overlap with logged sessions on the same day; don't double-count them.
- Respect the readiness call: never recommend adding load when readiness is HOLD or REDUCE.
- For cut/bulk/maintenance questions use the phase data (maintenance estimate, weight trend, plan checks).
  Keep rates within: cut 0.5-1.0% body weight/week, lean bulk 0.25-0.5%/week. If the maintenance
  estimate's confidence is low, say so. Help the athlete set goals together: ask what they want
  (strength, size, leanness, sport performance) and by when, then suggest a phase and plan.
- For training improvements use the intensity data (sets per week per muscle, RPE, e1RM trends).
  Typical productive ranges: ~10-20 working sets per muscle per week, most working sets around RPE 7-9.
- For running use the running data: keep ~80% of miles easy, raise weekly mileage ~10% at most, and
  place hard runs and heavy leg days so they don't stack on consecutive days.
- Practices, games and conditioning are logged with session-RPE load (RPE x minutes) in
  running.load. An acute:chronic ratio above 1.5 is a load spike: suggest easing lifting/running
  volume that week.{sport_line}
- Be concise, specific and encouraging. Use short paragraphs or bullet points. Plain text, no tables."""


# ==================================================
# Training load (lifting volume, running miles) per 7-day window
# ==================================================

def _windows(today: date, count: int):
    """[(start, end)] newest first; window 0 = the 7 days ending today."""
    return [
        (today - timedelta(days=7 * i + 6), today - timedelta(days=7 * i))
        for i in range(count)
    ]


def _lifting_entries():
    """(date, volume) for every lifting session/row, from both logs."""
    entries = []

    for session in get_workout_sessions():
        analysis = analyze_session_sets(session)
        volume = sum(e["total_volume"] for e in analysis["exercises"])
        entries.append((session["session_date"], volume))

    for workout_date, _exercise, weight, sets, reps, *_rest in get_workouts():
        entries.append((workout_date, calculate_volume(weight, sets, reps) or 0.0))

    return entries


def _running_entries():
    """(date, miles) from legacy runs and athletic sessions."""
    entries = [(run[0], run[1] or 0.0) for run in get_runs()]
    entries += [
        (s["session_date"], s["distance_miles"] or 0.0)
        for s in get_athletic_sessions()
        if s.get("distance_miles")
    ]
    return entries


def weekly_load(today: date | None = None, weeks: int = 4) -> list[dict]:
    today = today or date.today()
    lifting = _lifting_entries()
    running = _running_entries()
    result = []

    for start, end in _windows(today, weeks):
        s, e = start.isoformat(), end.isoformat()
        lift = [v for d, v in lifting if s <= d <= e]
        runs = [m for d, m in running if s <= d <= e]
        result.append(
            {
                "start": s,
                "end": e,
                "lifting_volume_lb": round(sum(lift), 1),
                "lifting_days": len({d for d, _ in lifting if s <= d <= e}),
                "running_miles": round(sum(runs), 2),
                "runs": len(runs),
            }
        )

    return result


def load_jump_flags(windows: list[dict]) -> list[dict]:
    """Flag a big jump in this week's load vs. the 3 weeks before."""

    if len(windows) < 2:
        return []

    flags = []
    current, previous = windows[0], windows[1:4]

    for metric, label, unit in (
        ("lifting_volume_lb", "Lifting volume", "lb"),
        ("running_miles", "Running mileage", "mi"),
    ):
        now = current[metric]
        baseline = mean(w[metric] for w in previous)

        if now <= 0:
            continue

        if baseline <= 0:
            flags.append(
                {
                    "metric": metric,
                    "severity": "info",
                    "message": f"{label}: {now:g} {unit} this week after ~3 quiet weeks. Ease back in.",
                }
            )
            continue

        pct = round((now - baseline) / baseline * 100)
        if pct >= JUMP_CAUTION_PCT:
            flags.append(
                {
                    "metric": metric,
                    "severity": "high" if pct >= JUMP_HIGH_PCT else "caution",
                    "change_pct": pct,
                    "message": (
                        f"{label} is up {pct}% vs. your 3-week average "
                        f"({now:g} vs. {baseline:.0f} {unit}). Increases above ~{JUMP_CAUTION_PCT}% a week "
                        "raise injury risk."
                    ),
                }
            )

    return flags


# ==================================================
# Recovery: your check-ins first, Garmin as optional extra
# ==================================================

def recovery_snapshot(today: date | None = None, garmin_db=None) -> dict:
    today = today or date.today()
    flags: list[dict] = []
    notes: list[str] = []

    # --- Manual check-in (primary) ---
    entries = get_recovery_entries(limit=1)
    checkin = entries[0] if entries else None
    checkin_fresh = False

    if checkin:
        age = (today - date.fromisoformat(checkin["recovery_date"])).days
        checkin_fresh = age <= RECOVERY_FRESH_DAYS
        if checkin_fresh:
            for f in get_recovery_flags(
                checkin["sleep_hours"], checkin["energy"], checkin["soreness"], checkin["pain"]
            ):
                flags.append({**f, "source": "check-in"})
        else:
            notes.append(f"Last recovery check-in was {age} days ago, so it isn't used for today.")
    else:
        notes.append("No recovery check-ins logged yet.")

    # --- Garmin (optional) ---
    garmin_rows = garmin_store.get_daily_recovery(
        (today - timedelta(days=14)).isoformat(), db_path=garmin_db
    )
    garmin_latest = None
    recent = [r for r in garmin_rows if r["date"] >= (today - timedelta(days=1)).isoformat()]

    if recent:
        garmin_latest = recent[-1]
        history = [r for r in garmin_rows if r["date"] < garmin_latest["date"]][-7:]

        sleep_s = garmin_latest.get("sleep_seconds")
        if sleep_s is not None and sleep_s / 3600 < RECOVERY_MIN_SLEEP_HOURS:
            hours = round(sleep_s / 3600, 1)
            flags.append(
                {"metric": "sleep_hours", "value": hours, "severity": "hold", "source": "Garmin",
                 "message": f"Garmin measured only {hours} hours of sleep"}
            )

        hrv = garmin_latest.get("hrv_overnight_avg")
        hrv_hist = [r["hrv_overnight_avg"] for r in history if r.get("hrv_overnight_avg") is not None]
        if hrv is not None and len(hrv_hist) >= 3:
            baseline = mean(hrv_hist)
            drop = round((baseline - hrv) / baseline * 100) if baseline else 0
            if drop >= HRV_DROP_PCT:
                flags.append(
                    {"metric": "hrv", "value": hrv, "severity": "hold", "source": "Garmin",
                     "message": f"overnight HRV is {drop}% below your 7-day baseline ({hrv:g} vs. {baseline:.0f} ms)"}
                )

        rhr = garmin_latest.get("resting_hr")
        rhr_hist = [r["resting_hr"] for r in history if r.get("resting_hr") is not None]
        if rhr is not None and len(rhr_hist) >= 3 and rhr - mean(rhr_hist) >= RESTING_HR_RISE_BPM:
            flags.append(
                {"metric": "resting_hr", "value": rhr, "severity": "hold", "source": "Garmin",
                 "message": f"resting heart rate is {rhr - mean(rhr_hist):.0f} bpm above your 7-day average"}
            )

    if any(f["severity"] == "reduce" for f in flags):
        readiness = "REDUCE"
    elif flags:
        readiness = "HOLD"
    elif checkin_fresh or garmin_latest:
        readiness = "GO"
    else:
        readiness = "UNKNOWN"

    return {
        "readiness": readiness,
        "flags": flags,
        "notes": notes,
        "checkin": checkin if checkin_fresh else None,
        "garmin_last_night": garmin_latest,
        "garmin_available": bool(garmin_rows),
    }


# ==================================================
# Next workout
# ==================================================

def _recent_sessions(today: date, days: int = 28) -> list[dict]:
    """Recent lifting sessions as {key, name, date, exercises[]}, newest first."""

    since = (today - timedelta(days=days)).isoformat()
    sessions = []

    for s in get_workout_sessions():
        if s["session_date"] < since:
            continue
        exercises = []
        for st in sorted(s["sets"], key=lambda x: x["id"]):
            if st["exercise_name"] not in exercises:
                exercises.append(st["exercise_name"])
        if exercises:
            sessions.append({"name": s["name"], "date": s["session_date"], "exercises": exercises})

    legacy_by_date: dict[str, list[str]] = {}
    for workout_date, exercise, *_rest in get_workouts():
        if workout_date >= since and exercise not in legacy_by_date.setdefault(workout_date, []):
            legacy_by_date[workout_date].append(exercise)
    for d, exercises in legacy_by_date.items():
        sessions.append({"name": None, "date": d, "exercises": exercises})

    for s in sessions:
        s["key"] = (s["name"] or "").strip().lower() or "|".join(sorted(e.lower() for e in s["exercises"]))

    return sorted(sessions, key=lambda s: s["date"], reverse=True)


def next_workout(today: date | None = None, readiness: str = "GO") -> dict | None:
    """
    Rotate through your recent session types: repeat the one you did
    longest ago, with each exercise's load from the progression rules,
    capped by today's readiness.
    """

    today = today or date.today()
    sessions = _recent_sessions(today)
    if not sessions:
        return None

    latest_per_key: dict[str, dict] = {}
    for s in sessions:  # newest first, so first seen = latest of that type
        latest_per_key.setdefault(s["key"], s)

    due = min(latest_per_key.values(), key=lambda s: s["date"]) if len(latest_per_key) > 1 else sessions[0]

    exercises = []
    for name in due["exercises"]:
        plan = get_next_weight(name)
        decision = plan["decision"]
        weight = plan["recommended_weight"]
        previous = plan["previous_weight"]
        note = plan["reason"]

        if readiness in ("HOLD", "REDUCE") and decision == "INCREASE":
            decision, weight = "HOLD", previous
            note = "Recovery says hold today, so no increase."
        if readiness == "REDUCE" and decision != "REDUCE" and previous:
            decision, weight = "REDUCE", round(previous * 0.9 / 5) * 5
            note = "Recovery says back off today: about 10% lighter."

        exercises.append(
            {"exercise": name, "decision": decision, "previous_weight": previous,
             "recommended_weight": weight, "reason": note}
        )

    return {
        "session_name": due["name"] or ", ".join(due["exercises"][:3]),
        "last_done": due["date"],
        "readiness": readiness,
        "exercises": exercises,
    }


# ==================================================
# Training summary + safety
# ==================================================

def training_summary(today: date | None = None, days: int = 14) -> dict:
    today = today or date.today()
    since = (today - timedelta(days=days - 1)).isoformat()
    sessions = _recent_sessions(today, days=days - 1)

    exercise_names = sorted({e for s in sessions for e in s["exercises"]})
    trends = []
    for name in exercise_names:
        t = get_exercise_trend(name)
        if t.get("trend"):
            trends.append(
                {"exercise": name, "trend": t["trend"], "latest_e1rm": t["latest_e1rm"],
                 "change_lb": t["change_lb"]}
            )

    nutrition_days = [get_daily_nutrition_totals((today - timedelta(days=i)).isoformat()) for i in range(7)]
    logged = [d for d in nutrition_days if d["calories"] > 0]
    target = get_nutrition_target_for(today.isoformat())

    return {
        "period": f"{since} to {today.isoformat()}",
        "lifting_sessions": len(sessions),
        "sessions": [{"date": s["date"], "name": s["name"], "exercises": s["exercises"]} for s in sessions],
        "strength_trends": trends,
        "runs": [
            {"date": d, "miles": m} for d, m in sorted(_running_entries()) if d >= since
        ],
        "nutrition_7d": {
            "days_logged": len(logged),
            "avg_calories": round(mean(d["calories"] for d in logged)) if logged else None,
            "avg_protein_g": round(mean(d["protein_g"] for d in logged)) if logged else None,
            "target_calories": target.get("calories") if target else None,
            "target_protein_g": target.get("protein_g") if target else None,
        },
        "body_weight": get_body_weight_summary(),
    }


def pain_reports(today: date | None = None, days: int = 14) -> list[dict]:
    """Pain at or above the threshold in recent sets or check-ins."""

    today = today or date.today()
    since = (today - timedelta(days=days - 1)).isoformat()
    reports = []

    for s in get_workout_sessions():
        if s["session_date"] < since:
            continue
        for st in s["sets"]:
            if (st.get("pain") or 0) >= RECOVERY_PAIN_REDUCE_AT:
                reports.append({"date": s["session_date"], "where": st["exercise_name"], "pain": st["pain"]})

    for workout_date, exercise, _w, _s, _r, _rpe, pain, *_ in get_workouts():
        if workout_date >= since and (pain or 0) >= RECOVERY_PAIN_REDUCE_AT:
            reports.append({"date": workout_date, "where": exercise, "pain": pain})

    for entry in get_recovery_entries(limit=60):
        if entry["recovery_date"] >= since and (entry["pain"] or 0) >= RECOVERY_PAIN_REDUCE_AT:
            reports.append({"date": entry["recovery_date"], "where": "recovery check-in", "pain": entry["pain"]})

    return sorted(reports, key=lambda r: r["date"], reverse=True)


# ==================================================
# Intensity + volume per lift and per muscle group
# ==================================================

# keyword -> muscle group (first match wins; checked in this order)
MUSCLE_KEYWORDS = [
    ("romanian", "hamstrings"), ("rdl", "hamstrings"), ("leg curl", "hamstrings"), ("hamstring", "hamstrings"),
    ("deadlift", "back/posterior chain"),
    ("squat", "quads"), ("leg press", "quads"), ("lunge", "quads"), ("leg extension", "quads"), ("split", "quads"),
    ("hip thrust", "glutes"), ("glute", "glutes"),
    ("calf", "calves"),
    ("bench", "chest"), ("chest", "chest"), ("fly", "chest"), ("push-up", "chest"), ("pushup", "chest"), ("dip", "chest"),
    ("overhead", "shoulders"), ("ohp", "shoulders"), ("shoulder", "shoulders"), ("lateral", "shoulders"), ("raise", "shoulders"),
    ("pull-up", "back"), ("pullup", "back"), ("chin", "back"), ("row", "back"), ("pulldown", "back"), ("lat ", "back"),
    ("curl", "biceps"),
    ("tricep", "triceps"), ("pushdown", "triceps"), ("skull", "triceps"), ("extension", "triceps"),
    ("plank", "core"), ("crunch", "core"), ("ab ", "core"), ("core", "core"),
]
HARD_SET_RPE = 7          # sets at/above this (or with no RPE logged) count as working sets
WEEKLY_SETS_RANGE = (10, 20)


def muscle_group(exercise: str) -> str:
    name = f" {exercise.lower()} "
    for keyword, group in MUSCLE_KEYWORDS:
        if keyword in name:
            return group
    return "other"


def training_intensity(today: date | None = None, days: int = 28) -> dict:
    """Per-lift intensity and weekly working sets per muscle, from per-set logs."""

    today = today or date.today()
    since = (today - timedelta(days=days - 1)).isoformat()
    weeks = days / 7
    per_lift: dict[str, dict] = {}
    group_sets: dict[str, int] = {}

    for session in get_workout_sessions():
        if session["session_date"] < since:
            continue
        for st in session["sets"]:
            if not st.get("is_completed", 1):
                continue
            name = st["exercise_name"]
            lift = per_lift.setdefault(name, {"sessions": set(), "sets": 0, "rpes": [], "best_e1rm": None, "top_by_date": {}})
            lift["sessions"].add(session["session_date"])
            lift["sets"] += 1
            if st.get("rpe") is not None:
                lift["rpes"].append(st["rpe"])
            e1rm = calculate_e1rm(st.get("weight"), st.get("reps"))
            if e1rm and (lift["best_e1rm"] is None or e1rm > lift["best_e1rm"]):
                lift["best_e1rm"] = e1rm
            # Top set (highest e1RM) of each session date.
            top = lift["top_by_date"].get(session["session_date"])
            if top is None or (e1rm or 0) > (top["e1rm"] or 0):
                lift["top_by_date"][session["session_date"]] = {
                    "weight": st.get("weight"), "reps": st.get("reps"), "rpe": st.get("rpe"), "e1rm": e1rm,
                }
            if st.get("rpe") is None or st["rpe"] >= HARD_SET_RPE:
                group = muscle_group(name)
                group_sets[group] = group_sets.get(group, 0) + 1

    lifts = []
    for name, lift in sorted(per_lift.items(), key=lambda kv: -kv[1]["sets"]):
        trend = get_exercise_trend(name)
        last = lift["top_by_date"][max(lift["top_by_date"])] if lift["top_by_date"] else {}
        lifts.append(
            {
                "exercise": name,
                "sessions": len(lift["sessions"]),
                "sets_per_week": round(lift["sets"] / weeks, 1),
                "avg_rpe": round(mean(lift["rpes"]), 1) if lift["rpes"] else None,
                "hard_set_share_pct": round(sum(r >= 8 for r in lift["rpes"]) / len(lift["rpes"]) * 100) if lift["rpes"] else None,
                "rpe_logged_pct": round(len(lift["rpes"]) / lift["sets"] * 100),
                "best_e1rm": lift["best_e1rm"],
                "e1rm_trend": trend.get("trend"),
                "e1rm_change_lb": trend.get("change_lb"),
                "last_top_set": (
                    f"{last['weight']:g} x {last['reps']}" + (f" @{last['rpe']:g}" if last.get("rpe") else "")
                    if last.get("weight") is not None and last.get("reps") else None
                ),
                "last_top_set_pct_of_best": (
                    round(last["e1rm"] / lift["best_e1rm"] * 100) if last.get("e1rm") and lift["best_e1rm"] else None
                ),
            }
        )

    lo, hi = WEEKLY_SETS_RANGE
    muscles = []
    for group, sets in sorted(group_sets.items(), key=lambda kv: -kv[1]):
        per_week = round(sets / weeks, 1)
        status = "low" if per_week < lo else "high" if per_week > hi else "in range"
        muscles.append({"muscle": group, "working_sets_per_week": per_week, "status": status})

    return {"window_days": days, "lifts": lifts, "muscle_groups": muscles, "sets_range_per_week": WEEKLY_SETS_RANGE}


SEE_A_PROFESSIONAL = (
    "You've logged pain of {pain}/10 recently ({where}, {date}). Stop any movement that hurts and "
    "get it checked by a doctor or physical therapist before loading it again."
)


def build_insights(today: date | None = None, garmin_db=None) -> dict:
    """Everything the coach knows, as plain data. No LLM involved."""

    today = today or date.today()
    windows = weekly_load(today)
    recovery = recovery_snapshot(today, garmin_db=garmin_db)
    pains = pain_reports(today)

    safety = []
    if pains:
        worst = max(pains, key=lambda p: p["pain"])
        safety.append(SEE_A_PROFESSIONAL.format(**worst))

    return {
        "today": today.isoformat(),
        "readiness": recovery["readiness"],
        "recovery": recovery,
        "load_by_week": windows,
        "load_flags": load_jump_flags(windows),
        "next_workout": next_workout(today, readiness=recovery["readiness"]),
        "summary": training_summary(today),
        "pain_reports": pains,
        "safety_notes": safety,
        "intensity": training_intensity(today),
        "running": running_analytics.summary(today),
        "garmin_activities_14d": garmin_store.get_recent_activities((today - timedelta(days=13)).isoformat(), db_path=garmin_db),
        "phase": phase_engine.phase_overview(today),
    }


# ==================================================
# LLM layer (localhost Ollama only)
# ==================================================

TASK_PROMPTS = {
    "summary": (
        "Summarize my last two weeks of training in under 150 words: what went well, "
        "what to watch, and anything the flags point out."
    ),
    "phase": (
        "Help me choose and run my training phase (cut, lean bulk, maintenance or recomp). Use the phase data: "
        "my maintenance estimate, weight trend, body fat if logged, profile, strength trends and any active plan. "
        "Recommend ONE phase with a weekly rate, explain why in plain words, say what would change your mind, "
        "and give 2-3 training priorities for that phase. If key info is missing (goal, body fat, profile), "
        "ask me for it. Under 220 words."
    ),
    "improve": (
        "Coach me on my lifting using the intensity data: which lifts are progressing or stalling, whether my "
        "effort (RPE) and weekly sets per muscle look right for my current phase, and the 3 most useful changes "
        "for the next 2-4 weeks. Under 220 words."
    ),
    "next_workout": (
        "Explain my next workout from the DATA in under 150 words: list each exercise with its "
        "recommended load, say why, and give one cue for the session. Follow the readiness call."
    ),
}


def ask_coach(
    task: str,
    model: str,
    question: str | None = None,
    history: list[dict] | None = None,
    insights: dict | None = None,
) -> dict:
    """Run one coach request against the local model. Returns {text, insights}."""

    insights = insights or build_insights()
    data_block = json.dumps(insights, default=str, separators=(",", ":"))

    messages = [
        {"role": "system", "content": system_prompt()},
        {"role": "system", "content": f"DATA (computed by the app, today is {insights['today']}):\n{data_block}"},
    ]

    for turn in (history or [])[-10:]:
        if turn.get("role") in ("user", "assistant") and isinstance(turn.get("content"), str):
            messages.append({"role": turn["role"], "content": turn["content"][:4000]})

    if task == "chat":
        if not question or not question.strip():
            raise ValueError("A question is required.")
        messages.append({"role": "user", "content": question.strip()[:4000]})
    elif task in TASK_PROMPTS:
        messages.append({"role": "user", "content": TASK_PROMPTS[task]})
    else:
        raise ValueError(f"Unknown coach task: {task}")

    response = local_llm.chat(model, messages, think="low", options={"num_predict": 1500})
    return {"text": response.message.content.strip(), "insights": insights}
