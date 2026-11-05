"""
Weekly planner built from YOUR training — deterministic, no LLM.

- Lifting days rotate through the session types you've actually done in
  the last 4 weeks (e.g. "Push day", "Lower A"), using your exercises,
  your usual sets x reps, and loads from the progression rules.
  With no history yet, a starter template is used (no loads).
- Running follows what you've been doing: same number of runs, weekly
  miles up at most 10% (held flat on a cut), ~80% easy, long run on the
  weekend, the quality run kept away from heavy leg days.
- Training days default to your Goals & Phase plan (or 4 days).
- Completion is detected from your logs; you can also tick items off.
"""

import json
import sqlite3
from collections import Counter
from datetime import date, timedelta
from statistics import mean

import src.database_v2 as database_v2
from src import phase_engine, running_analytics
from src.weekly_planner import get_next_weight, get_strength_template

LOWER_KEYWORDS = ("squat", "deadlift", "rdl", "lunge", "leg", "split", "hip thrust", "calf", "step-up")
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DEFAULT_DAYS = {2: [0, 3], 3: [0, 2, 4], 4: [0, 1, 3, 4], 5: [0, 1, 2, 4, 5], 6: [0, 1, 2, 3, 4, 5], 7: list(range(7))}
MILEAGE_STEP = 1.10
LONG_RUN_SHARE = 0.3
QUALITY_SHARE = 0.2


def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def default_training_days(count: int | None) -> list[int]:
    return DEFAULT_DAYS.get(max(2, min(7, count or 4)))


# --------------------------------------------------
# What you've been doing
# --------------------------------------------------

def recent_session_types(today: date, days: int = 28) -> list[dict]:
    """Distinct session types from per-set logs, least recently done first."""

    since = (today - timedelta(days=days)).isoformat()
    by_key: dict[str, dict] = {}

    for s in sorted(database_v2.get_workout_sessions(), key=lambda x: x["session_date"]):
        if s["session_date"] < since or not s["sets"]:
            continue
        order: list[str] = []
        sets_per: Counter = Counter()
        reps_per: dict[str, list[int]] = {}
        for st in sorted(s["sets"], key=lambda x: x["id"]):
            name = st["exercise_name"]
            if name not in order:
                order.append(name)
            sets_per[name] += 1
            if st.get("reps"):
                reps_per.setdefault(name, []).append(int(st["reps"]))
        key = (s["name"] or "").strip().lower() or "|".join(sorted(e.lower() for e in order))
        by_key[key] = {  # later sessions overwrite: keep the latest version of each type
            "name": s["name"] or ", ".join(order[:3]),
            "last_done": s["session_date"],
            "exercises": [
                {
                    "exercise": e,
                    "sets": sets_per[e],
                    "reps": Counter(reps_per.get(e, [])).most_common(1)[0][0] if reps_per.get(e) else None,
                }
                for e in order
            ],
        }

    return sorted(by_key.values(), key=lambda t: t["last_done"])


def is_lower_session(session: dict) -> bool:
    names = " ".join(e["exercise"].lower() for e in session["exercises"])
    return sum(k in names for k in LOWER_KEYWORDS) >= max(1, len(session["exercises"]) // 2)


def running_profile(today: date) -> dict | None:
    weeks = running_analytics.weekly_mileage(running_analytics.all_sessions(), today, weeks=5)[:-1]  # 4 full weeks before this one
    active = [w for w in weeks if w["miles"] > 0]
    if not active:
        return None
    return {
        "avg_runs": round(mean(w["runs"] for w in active)),
        "last_week_miles": weeks[-1]["miles"],
        "avg_miles": round(mean(w["miles"] for w in active), 1),
        "longest_recent": max(w["long_run"] for w in weeks),
    }


# --------------------------------------------------
# Availability (your usual week)
# --------------------------------------------------

STATUSES = ("open", "busy", "practice", "game")
STATUS_LABEL = {"practice": "Practice", "game": "Game day"}


def get_availability() -> list[dict]:
    """Your usual week, Monday first. Days not set are open."""
    conn = sqlite3.connect(database_v2.DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = {r["weekday"]: dict(r) for r in conn.execute("SELECT * FROM weekly_availability")}
    conn.close()
    return [rows.get(i, {"weekday": i, "status": "open", "note": None}) for i in range(7)]


def save_availability(days: list[dict]) -> list[dict]:
    conn = sqlite3.connect(database_v2.DB_PATH)
    with conn:
        for d in days:
            conn.execute(
                """
                INSERT INTO weekly_availability (weekday, status, note) VALUES (?, ?, ?)
                ON CONFLICT (weekday) DO UPDATE SET status = excluded.status, note = excluded.note
                """,
                (d["weekday"], d["status"], d.get("note")),
            )
    conn.close()
    return get_availability()


def pick_lift_days(count: int, statuses: list[str]) -> list[int]:
    """Spread `count` lifting days over open days (practice days only if needed)."""
    allowed_open = [i for i in range(7) if statuses[i] == "open"]
    allowed_practice = [i for i in range(7) if statuses[i] == "practice"]
    preferred = [i for i in DEFAULT_DAYS.get(max(2, min(7, count)), []) if i in allowed_open]
    picked = preferred[:count]
    for pool in (allowed_open, allowed_practice):
        for i in pool:
            if len(picked) >= count:
                break
            if i not in picked:
                picked.append(i)
    return sorted(picked)


# --------------------------------------------------
# Build the week
# --------------------------------------------------

def build_week(
    week_start: date,
    training_days: list[int] | None = None,
    today: date | None = None,
    availability: list[str] | None = None,
) -> dict:
    today = today or date.today()
    week_start = monday_of(week_start)
    dates = [week_start + timedelta(days=i) for i in range(7)]
    plan = phase_engine.get_active_plan()
    statuses = availability or [d["status"] for d in get_availability()]
    notes: list[str] = []

    games = {i for i in range(7) if statuses[i] == "game"}
    practices = {i for i in range(7) if statuses[i] == "practice"}
    basketball_days = games | practices
    before_game = {i - 1 for i in games if i > 0}

    # ---- Which days you lift ----
    if training_days is None:
        lift_days = pick_lift_days((plan and plan.get("training_days_per_week")) or 4, statuses)
    else:
        lift_days = sorted({d for d in training_days if statuses[d] in ("open", "practice")})
        dropped = sorted(set(training_days) - set(lift_days))
        if dropped:
            names = ", ".join(DAY_NAMES[d] for d in dropped)
            notes.append(f"No lifting on {names}: marked busy or game day.")

    days = []
    for i, d in enumerate(dates):
        day = {"date": d.isoformat(), "focus": "Rest", "items": [], "status": statuses[i]}
        if i in basketball_days:
            day["items"].append(
                {"category": "basketball", "session_type": "Game" if i in games else "Practice",
                 "planned_work": "", "target": "Log minutes and RPE afterwards"}
            )
            day["focus"] = STATUS_LABEL[statuses[i]]
        elif statuses[i] == "busy":
            day["focus"] = "Busy"
        days.append(day)

    # ---- Lifting: rotate your sessions, keep legs away from games ----
    types = recent_session_types(today)
    if types:
        rotation = [types[i % len(types)] for i in range(len(lift_days))]
    else:
        template = get_strength_template()
        starter = [
            {"name": "Lower strength", "exercises": template["lower_strength"]},
            {"name": "Upper strength", "exercises": template["upper_strength"]},
            {"name": "Lower power", "exercises": template["lower_power"]},
            {"name": "Upper power", "exercises": template["upper_power"]},
        ]
        rotation = [starter[i % len(starter)] for i in range(len(lift_days))]
        notes.append("No recent lifting logged, so a starter template is used. Pick loads that feel like RPE 7.")

    # Swap a leg session off a pre-game or practice day when an upper session can take its place.
    bad_for_legs = before_game | practices
    for idx, weekday in enumerate(lift_days):
        if weekday in bad_for_legs and is_lower_session(rotation[idx]):
            for j in range(idx + 1, len(lift_days)):
                if lift_days[j] not in bad_for_legs and not is_lower_session(rotation[j]):
                    rotation[idx], rotation[j] = rotation[j], rotation[idx]
                    break
            # If no swap is possible, the leg session stays and is made light below.

    for weekday, session in zip(lift_days, rotation):
        day = days[weekday]
        lower = is_lower_session(session)
        light = lower and weekday in before_game
        day["focus"] = session["name"] if weekday not in basketball_days else f"{session['name']} + {STATUS_LABEL[statuses[weekday]].lower()}"
        day["lower"] = lower
        if light:
            notes.append(f"{DAY_NAMES[weekday]}: legs the day before a game, so loads are ~10% lighter at RPE 6.")
        for ex in session["exercises"]:
            rec = get_next_weight(ex["exercise"])
            weight = rec["recommended_weight"] if rec["decision"] not in ("NO_HISTORY",) else None
            if light and weight:
                weight = round(weight * 0.9 / 5) * 5
            day["items"].append(
                {
                    "category": "strength",
                    "exercise": ex["exercise"],
                    "prescribed_weight": weight,
                    "sets": ex.get("sets") or 3,
                    "reps": ex.get("reps") or 5,
                    "target_rpe": 6 if light else (ex.get("target_rpe") or 8),
                    "rest": ex.get("rest") or ("2-3 min" if (ex.get("reps") or 5) <= 5 else "90 sec"),
                    "notes": (
                        "Light: game tomorrow" if light else
                        f"{rec['decision'].title()} (last time {rec['previous_weight']:g} lb)"
                        if weight is not None and rec.get("previous_weight") is not None else None
                    ),
                }
            )

    # ---- Running: basketball days count as conditioning ----
    run = running_profile(today)
    if run and run["avg_runs"] > 0:
        cutting = bool(plan and plan["phase"] == "cut")
        base = max(run["last_week_miles"], run["avg_miles"] * 0.8)
        target = round(base * (1.0 if cutting else MILEAGE_STEP), 1)
        if cutting:
            notes.append("On a cut, running mileage is held flat rather than increased.")

        usual_runs = max(1, min(6, run["avg_runs"]))
        n_runs = max(0, usual_runs - len(basketball_days))
        if basketball_days:
            target = round(target * n_runs / usual_runs, 1)

        if n_runs == 0:
            notes.append("Basketball covers your conditioning this week, so no runs are planned.")
        else:
            long_miles = round(min(target * LONG_RUN_SHARE, max(run["longest_recent"] * MILEAGE_STEP, 2)), 1) if n_runs >= 2 else None
            # Two or more basketball days already bring plenty of hard running.
            quality_miles = round(target * QUALITY_SHARE, 1) if n_runs >= 3 and len(basketball_days) < 2 else None
            easy_count = n_runs - (1 if long_miles else 0) - (1 if quality_miles else 0)
            easy_miles = round((target - (long_miles or 0) - (quality_miles or 0)) / easy_count, 1) if easy_count else None
            if long_miles and easy_miles and easy_miles > long_miles:
                even = round((target - (quality_miles or 0)) / (easy_count + 1), 1)
                long_miles = easy_miles = even

            lower_days = {i for i, d in enumerate(days) if d.get("lower")}
            blocked = basketball_days | before_game | {i for i in range(7) if statuses[i] == "busy"}
            free = [i for i in range(7) if not days[i]["items"] and i not in blocked]
            others = [i for i in range(7) if i not in free and i not in blocked and i not in lower_days]
            order_pref = free + others + [i for i in sorted(lower_days) if i not in blocked]
            used: set[int] = set()

            def place(preferred: list[int]) -> int | None:
                for i in preferred:
                    if i not in used:
                        used.add(i)
                        return i
                return None

            def add_run(i: int | None, kind: str, miles: float, target_text: str):
                if i is None:
                    notes.append(f"No free day for the {kind.lower()} run this week.")
                    return
                days[i]["items"].append(
                    {"category": "running", "session_type": kind, "planned_work": f"{miles:g} mi", "target": target_text}
                )
                if days[i]["focus"] == "Rest":
                    days[i]["focus"] = f"{kind} run"

            if long_miles:
                add_run(place([i for i in (6, 5) if i in order_pref] + order_pref), "Long", long_miles, "Easy, conversational pace")
            if quality_miles:
                safe = [i for i in order_pref if not ({i - 1, i, i + 1} & lower_days)]
                add_run(place(safe + order_pref), "Tempo", quality_miles, "Comfortably hard (RPE 7), after a 1 mi warm-up")
            for _ in range(easy_count):
                add_run(place(order_pref), "Easy", easy_miles, "Easy pace (RPE 3-4), can hold a conversation")
            extra = f", fewer than usual because of {len(basketball_days)} basketball day(s)" if basketball_days else ""
            notes.append(f"Running: {n_runs} run(s), about {target:g} mi{extra} (last week {run['last_week_miles']:g} mi).")

    for d in days:
        if d["focus"] == "Rest" and not d["items"]:
            d["focus"] = "Rest / mobility"
        d.pop("lower", None)

    return {"week_start": week_start.isoformat(), "training_days": lift_days, "statuses": statuses, "days": days, "notes": notes}


# --------------------------------------------------
# Save / load / complete
# --------------------------------------------------

def _conn():
    conn = sqlite3.connect(database_v2.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def save_week(week: dict) -> int:
    """Replace any saved plan for the same week with this one."""
    start = week["week_start"]
    end = (date.fromisoformat(start) + timedelta(days=6)).isoformat()
    conn = _conn()
    with conn:
        for row in conn.execute("SELECT id FROM weekly_plans WHERE start_date = ?", (start,)).fetchall():
            conn.execute("DELETE FROM weekly_plan_items WHERE plan_id = ?", (row["id"],))
            conn.execute("DELETE FROM weekly_plans WHERE id = ?", (row["id"],))
        focus = [{"date": d["date"], "focus": d["focus"], "status": d.get("status", "open")} for d in week["days"]]
        plan_id = conn.execute(
            "INSERT INTO weekly_plans (week_number, start_date, end_date, focus_json, notes_json) VALUES (?, ?, ?, ?, ?)",
            (date.fromisoformat(start).isocalendar()[1], start, end, json.dumps(focus), json.dumps(week.get("notes", []))),
        ).lastrowid
        for d in week["days"]:
            for it in d["items"]:
                conn.execute(
                    """
                    INSERT INTO weekly_plan_items (plan_id, item_date, category, exercise, prescribed_weight, sets, reps,
                        rest, target_rpe, session_type, planned_work, target, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (plan_id, d["date"], it["category"], it.get("exercise"), it.get("prescribed_weight"), it.get("sets"),
                     it.get("reps"), it.get("rest"), it.get("target_rpe"), it.get("session_type"), it.get("planned_work"),
                     it.get("target"), it.get("notes")),
                )
    conn.close()
    return plan_id


def _logged_on(day: str) -> dict:
    """What you actually logged on a date (for auto-completion)."""
    lifts = {
        st["exercise_name"].lower()
        for s in database_v2.get_workout_sessions()
        if s["session_date"] == day
        for st in s["sets"]
    }
    sessions = [s for s in running_analytics.all_sessions() if s["session_date"] == day]
    ran = any(s["session_type"] == "running" for s in sessions)
    hooped = any(s["session_type"] == "basketball" for s in sessions)
    return {"lifts": lifts, "ran": ran, "basketball": hooped}


def get_week(week_start: date) -> dict | None:
    start = monday_of(week_start).isoformat()
    conn = _conn()
    plan = conn.execute("SELECT * FROM weekly_plans WHERE start_date = ? ORDER BY id DESC LIMIT 1", (start,)).fetchone()
    if plan is None:
        conn.close()
        return None
    items = [dict(r) for r in conn.execute("SELECT * FROM weekly_plan_items WHERE plan_id = ? ORDER BY item_date, id", (plan["id"],))]
    conn.close()

    saved_days = {f["date"]: f for f in json.loads(plan["focus_json"] or "[]")}
    days = []
    for i in range(7):
        d = (date.fromisoformat(start) + timedelta(days=i)).isoformat()
        logged = _logged_on(d)
        day_items = []
        for it in (x for x in items if x["item_date"] == d):
            auto = (
                (it["category"] == "strength" and (it["exercise"] or "").lower() in logged["lifts"])
                or (it["category"] == "running" and logged["ran"])
                or (it["category"] == "basketball" and logged["basketball"])
            )
            day_items.append({**it, "auto_completed": auto, "done": bool(it["is_completed"]) or auto})
        saved = saved_days.get(d, {})
        days.append({"date": d, "focus": saved.get("focus", "Rest / mobility"), "status": saved.get("status", "open"), "items": day_items})

    all_items = [it for d in days for it in d["items"]]
    return {
        "id": plan["id"],
        "week_start": start,
        "created_at": plan["created_at"],
        "days": days,
        "notes": json.loads(plan["notes_json"] or "[]"),
        "done": sum(it["done"] for it in all_items),
        "total": len(all_items),
    }


def update_item(item_id: int, fields: dict) -> bool:
    allowed = ["item_date", "exercise", "prescribed_weight", "sets", "reps", "target_rpe", "planned_work", "target", "notes", "is_completed"]
    cols = [c for c in allowed if c in fields]
    if not cols:
        return False
    conn = _conn()
    with conn:
        n = conn.execute(
            f"UPDATE weekly_plan_items SET {', '.join(f'{c} = ?' for c in cols)} WHERE id = ?",
            [fields[c] for c in cols] + [item_id],
        ).rowcount
    conn.close()
    return n > 0


def delete_item(item_id: int) -> bool:
    conn = _conn()
    with conn:
        n = conn.execute("DELETE FROM weekly_plan_items WHERE id = ?", (item_id,)).rowcount
    conn.close()
    return n > 0


def to_workbook_plan(week: dict) -> dict:
    """Shape a saved week for the existing Excel exporter."""
    overview, strength, running = [], [], []
    for d in week["days"]:
        when = date.fromisoformat(d["date"])
        overview.append({"date": when, "focus": d["focus"], "goal": ""})
        for it in d["items"]:
            if it["category"] == "strength":
                strength.append({"date": when, "exercise": it["exercise"], "weight": it["prescribed_weight"], "sets": it["sets"],
                                 "reps": it["reps"], "rest": it["rest"], "target_rpe": it["target_rpe"]})
            else:
                label = f"Basketball {it['session_type'].lower()}" if it["category"] == "basketball" else f"{it['session_type']} run"
                running.append({"date": when, "session_type": label, "planned_work": it["planned_work"],
                                "target": it["target"]})
    return {"overview": overview, "strength": strength, "running": running}
