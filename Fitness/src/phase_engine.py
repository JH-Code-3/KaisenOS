"""
Cut / bulk / maintain / recomp planning — all math, no LLM.

- Maintenance calories are estimated from YOUR data: average logged
  intake minus the energy implied by your weight trend (~3,500 kcal per
  lb). If there isn't enough data yet, a standard formula
  (Mifflin-St Jeor x activity) is used from your profile, clearly marked.
- Phase targets use widely used evidence-based ranges:
    cut      lose 0.5–1.0% body weight/week, protein ~1.0 g/lb
    bulk     gain 0.25–0.5%/week (lean bulk), protein ~0.8 g/lb
    maintain hold weight, protein ~0.8 g/lb
    recomp   hold weight or lose very slowly, protein ~1.0 g/lb
- Progress checks compare your actual rate, intake and strength trend
  against the active plan.
"""

import json
import sqlite3
from datetime import date, timedelta
from statistics import mean

import src.database_v2 as database_v2
from src.analytics import get_body_weight_history, get_exercise_trend
from src.database_v2 import get_daily_nutrition_totals

KCAL_PER_LB = 3500

PHASES = {
    "cut": {"label": "Cut", "rate_range": (-1.0, -0.5), "default_rate": -0.75, "protein_per_lb": 1.0},
    "bulk": {"label": "Lean bulk", "rate_range": (0.25, 0.5), "default_rate": 0.25, "protein_per_lb": 0.8},
    "maintain": {"label": "Maintenance", "rate_range": (0.0, 0.0), "default_rate": 0.0, "protein_per_lb": 0.8},
    "recomp": {"label": "Recomp", "rate_range": (-0.25, 0.0), "default_rate": -0.1, "protein_per_lb": 1.0},
}
FAT_PER_LB_MIN = 0.3            # keep dietary fat at or above ~0.3 g/lb
LONG_CUT_WEEKS = 12             # suggest a maintenance break after this
MIN_INTAKE_DAYS = 10
MIN_WEIGH_INS = 4
MIN_WEIGHT_SPAN_DAYS = 10


# --------------------------------------------------
# Profile
# --------------------------------------------------

def _conn():
    conn = sqlite3.connect(database_v2.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


SPORTS = ["lifting", "running", "basketball", "other"]


def _sports_from_logs() -> list[str]:
    """When no sports are chosen yet, infer them from what's been logged."""
    conn = _conn()
    found = []
    if conn.execute("SELECT 1 FROM workout_sessions LIMIT 1").fetchone() or conn.execute("SELECT 1 FROM workouts LIMIT 1").fetchone():
        found.append("lifting")
    types = {r[0] for r in conn.execute("SELECT DISTINCT session_type FROM athletic_sessions")}
    if "running" in types or conn.execute("SELECT 1 FROM running LIMIT 1").fetchone():
        found.append("running")
    if "basketball" in types:
        found.append("basketball")
    conn.close()
    return found


def get_profile() -> dict:
    conn = _conn()
    row = conn.execute("SELECT sex, birth_year, height_in, experience, sports FROM athlete_profile WHERE id = 1").fetchone()
    conn.close()
    profile = dict(row) if row else {"sex": None, "birth_year": None, "height_in": None, "experience": None, "sports": None}
    chosen = json.loads(profile["sports"]) if profile.get("sports") else None
    profile["sports"] = chosen
    # What the app uses: your choice, or what your logs show.
    profile["effective_sports"] = chosen if chosen is not None else _sports_from_logs()
    return profile


def save_profile(sex=None, birth_year=None, height_in=None, experience=None, sports=None) -> dict:
    sports_json = json.dumps([s for s in SPORTS if s in sports]) if sports is not None else None
    conn = _conn()
    with conn:
        conn.execute(
            """
            INSERT INTO athlete_profile (id, sex, birth_year, height_in, experience, sports, updated_at)
            VALUES (1, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT (id) DO UPDATE SET sex = excluded.sex, birth_year = excluded.birth_year,
                height_in = excluded.height_in, experience = excluded.experience,
                sports = excluded.sports, updated_at = excluded.updated_at
            """,
            (sex, birth_year, height_in, experience, sports_json),
        )
    conn.close()
    return get_profile()


# --------------------------------------------------
# Energy balance from your logs
# --------------------------------------------------

def _slope_per_day(points: list[tuple[date, float]]) -> float:
    """Least-squares slope (lb/day) — less noisy than first-vs-last."""
    xs = [(d - points[0][0]).days for d, _ in points]
    ys = [w for _, w in points]
    mx, my = mean(xs), mean(ys)
    denom = sum((x - mx) ** 2 for x in xs)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom if denom else 0.0


def formula_maintenance(weight_lb: float | None, profile: dict, today: date) -> float | None:
    """Mifflin-St Jeor x 1.55 (moderately active). Needs sex, age, height."""
    if not weight_lb or not profile.get("height_in") or not profile.get("birth_year") or profile.get("sex") not in ("male", "female"):
        return None
    kg = weight_lb / 2.20462
    cm = profile["height_in"] * 2.54
    age = today.year - profile["birth_year"]
    bmr = 10 * kg + 6.25 * cm - 5 * age + (5 if profile["sex"] == "male" else -161)
    return round(bmr * 1.55 / 10) * 10


def energy_balance(today: date | None = None, days: int = 28) -> dict:
    today = today or date.today()
    since = today - timedelta(days=days - 1)

    intake_days = [get_daily_nutrition_totals((since + timedelta(days=i)).isoformat()) for i in range(days)]
    logged = [d for d in intake_days if d["calories"] > 0]
    avg_intake = round(mean(d["calories"] for d in logged)) if logged else None
    avg_protein = round(mean(d["protein_g"] for d in logged)) if logged else None

    weigh_ins = sorted(
        (date.fromisoformat(h["date"]), h["body_weight"])
        for h in get_body_weight_history()
        if date.fromisoformat(h["date"]) >= since
    )
    latest_weight = weigh_ins[-1][1] if weigh_ins else next(
        (h["body_weight"] for h in get_body_weight_history()), None
    )

    weekly_change = weekly_change_pct = None
    span = (weigh_ins[-1][0] - weigh_ins[0][0]).days if len(weigh_ins) >= 2 else 0
    if len(weigh_ins) >= MIN_WEIGH_INS and span >= MIN_WEIGHT_SPAN_DAYS:
        per_day = _slope_per_day(weigh_ins)
        weekly_change = round(per_day * 7, 2)
        if latest_weight:
            weekly_change_pct = round(weekly_change / latest_weight * 100, 2)

    profile = get_profile()
    maintenance = None
    method = None
    if avg_intake and weekly_change is not None and len(logged) >= MIN_INTAKE_DAYS:
        maintenance = round((avg_intake - weekly_change / 7 * KCAL_PER_LB) / 10) * 10
        method = "your logs"
    else:
        maintenance = formula_maintenance(latest_weight, profile, today)
        method = "formula (not enough logged data yet)" if maintenance else None

    coverage = round(len(logged) / days * 100)
    if method == "your logs":
        confidence = "high" if len(logged) >= 20 and len(weigh_ins) >= 8 else "medium"
    else:
        confidence = "low" if maintenance else "none"

    notes = []
    if logged and coverage < 70:
        notes.append(
            f"Meals were logged on {len(logged)} of {days} days. Unlogged days aren't counted, so make sure "
            "the days you did log are complete."
        )
    if len(weigh_ins) < MIN_WEIGH_INS:
        notes.append("Weigh in at least 3–4 times a week (same time, after waking) for a reliable trend.")

    return {
        "window_days": days,
        "days_logged": len(logged),
        "avg_intake": avg_intake,
        "avg_protein_g": avg_protein,
        "weigh_ins": len(weigh_ins),
        "latest_weight": latest_weight,
        "weekly_change_lb": weekly_change,
        "weekly_change_pct": weekly_change_pct,
        "maintenance_kcal": maintenance,
        "maintenance_method": method,
        "confidence": confidence,
        "notes": notes,
    }


# --------------------------------------------------
# Plans
# --------------------------------------------------

def compute_plan(
    phase: str,
    body_weight: float,
    maintenance: float,
    weekly_rate_pct: float | None = None,
    target_weight: float | None = None,
) -> dict:
    """Calories and macros for a phase. Pure math, no data access."""

    spec = PHASES[phase]
    lo, hi = spec["rate_range"]
    rate = spec["default_rate"] if weekly_rate_pct is None else weekly_rate_pct
    warnings = []
    if not (lo - 1e-9 <= rate <= hi + 1e-9):
        warnings.append(
            f"{rate:+.2f}%/week is outside the usual {spec['label'].lower()} range "
            f"({lo:+.2f} to {hi:+.2f}%/week)."
        )

    weekly_lb = body_weight * rate / 100
    daily_delta = weekly_lb * KCAL_PER_LB / 7
    calories = round((maintenance + daily_delta) / 10) * 10

    # Protein on a cut is based on goal weight when it's lower (avoids huge numbers at high body fat).
    protein_basis = min(body_weight, target_weight) if (phase in ("cut", "recomp") and target_weight) else body_weight
    protein = round(protein_basis * spec["protein_per_lb"] / 5) * 5
    fat = round(max(body_weight * FAT_PER_LB_MIN, calories * 0.25 / 9) / 5) * 5
    carbs = max(0, round((calories - protein * 4 - fat * 9) / 4 / 5) * 5)

    if calories < 1500:
        warnings.append("Under 1,500 kcal/day is very aggressive. Consider a slower rate.")

    weeks_to_target = None
    if target_weight and weekly_lb:
        weeks = (target_weight - body_weight) / weekly_lb
        weeks_to_target = round(weeks, 1) if weeks > 0 else None
        if weeks <= 0:
            warnings.append("The target weight is in the other direction from this phase.")

    return {
        "phase": phase,
        "weekly_rate_pct": round(rate, 2),
        "weekly_change_lb": round(weekly_lb, 2),
        "calorie_target": calories,
        "daily_energy_delta": round(daily_delta),
        "protein_g": protein,
        "fat_g": fat,
        "carbs_g": carbs,
        "weeks_to_target": weeks_to_target,
        "warnings": warnings,
    }


def get_active_plan() -> dict | None:
    conn = _conn()
    row = conn.execute("SELECT * FROM coach_plans WHERE status = 'active' ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    return dict(row) if row else None


def save_plan(plan: dict, today: date | None = None) -> dict:
    """Archive the current plan, save the new one, and set matching nutrition targets."""

    today = today or date.today()
    conn = _conn()
    with conn:
        conn.execute("UPDATE coach_plans SET status = 'archived' WHERE status = 'active'")
        conn.execute(
            """
            INSERT INTO coach_plans (phase, start_date, start_weight, target_weight, target_date, weekly_rate_pct,
                calorie_target, protein_g, carbs_g, fat_g, training_days_per_week, priorities, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (plan["phase"], today.isoformat(), plan.get("start_weight"), plan.get("target_weight"),
             plan.get("target_date"), plan["weekly_rate_pct"], plan["calorie_target"], plan["protein_g"],
             plan["carbs_g"], plan["fat_g"], plan.get("training_days_per_week"), plan.get("priorities"),
             plan.get("notes")),
        )
        conn.execute(
            """
            INSERT INTO nutrition_targets (effective_date, calories, protein_g, carbs_g, fat_g, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (today.isoformat(), plan["calorie_target"], plan["protein_g"], plan["carbs_g"], plan["fat_g"],
             f"From {PHASES[plan['phase']]['label'].lower()} plan"),
        )
    conn.close()
    return get_active_plan()


def end_plan() -> bool:
    conn = _conn()
    with conn:
        changed = conn.execute("UPDATE coach_plans SET status = 'archived' WHERE status = 'active'").rowcount
    conn.close()
    return changed > 0


# --------------------------------------------------
# Progress + phase guidance
# --------------------------------------------------

def plan_progress(plan: dict, balance: dict, strength_trends: list[dict], today: date) -> dict:
    weeks_in = (today - date.fromisoformat(plan["start_date"])).days / 7
    target_rate = plan["weekly_rate_pct"] or 0
    actual_rate = balance["weekly_change_pct"]
    checks = []

    if actual_rate is None:
        checks.append({"status": "unknown", "message": "Not enough weigh-ins yet to judge the rate."})
    else:
        diff = actual_rate - target_rate
        if abs(diff) <= 0.25:
            checks.append({"status": "good", "message": f"Weight is moving {actual_rate:+.2f}%/week — on target ({target_rate:+.2f}%)."})
        elif plan["phase"] == "cut" and actual_rate < -1.25:
            checks.append({"status": "warn", "message": f"Losing {abs(actual_rate):.2f}%/week — faster than ideal. Add ~150–200 kcal/day to protect muscle."})
        elif diff > 0.25:
            checks.append({"status": "warn", "message": f"Weight is moving {actual_rate:+.2f}%/week vs. the {target_rate:+.2f}% target. Trim ~150–200 kcal/day if this holds another week."})
        else:
            checks.append({"status": "warn", "message": f"Weight is moving {actual_rate:+.2f}%/week vs. the {target_rate:+.2f}% target. Add ~150–200 kcal/day if this holds another week."})

    if balance["avg_intake"] and plan["calorie_target"]:
        off = (balance["avg_intake"] - plan["calorie_target"]) / plan["calorie_target"] * 100
        checks.append({
            "status": "good" if abs(off) <= 10 else "warn",
            "message": f"Average intake {balance['avg_intake']:,} kcal vs. target {plan['calorie_target']:,.0f} ({off:+.0f}%).",
        })
    if balance["avg_protein_g"] and plan["protein_g"]:
        ratio = balance["avg_protein_g"] / plan["protein_g"]
        checks.append({
            "status": "good" if ratio >= 0.9 else "warn",
            "message": f"Protein averaging {balance['avg_protein_g']} g vs. {plan['protein_g']:.0f} g target.",
        })

    declining = [t for t in strength_trends if t.get("trend") == "declining"]
    if plan["phase"] == "cut" and strength_trends and len(declining) > len(strength_trends) / 2:
        checks.append({"status": "warn", "message": "Most lifts are trending down on this cut. Consider a smaller deficit or a short maintenance break."})
    if plan["phase"] == "cut" and weeks_in >= LONG_CUT_WEEKS:
        checks.append({"status": "warn", "message": f"You've been cutting for {weeks_in:.0f} weeks. A 1–2 week maintenance break can help recovery and adherence."})

    return {"weeks_in": round(weeks_in, 1), "checks": checks}


def phase_hints(profile: dict, latest_body_fat: float | None, balance: dict) -> list[str]:
    """Deterministic starting points for the cut/bulk/maintain conversation."""
    hints = []
    sex = profile.get("sex")
    if latest_body_fat is not None and sex in ("male", "female"):
        high, low = (20, 12) if sex == "male" else (30, 22)
        if latest_body_fat >= high:
            hints.append(f"Body fat {latest_body_fat}% is on the higher side for {sex}s: a cut usually comes first.")
        elif latest_body_fat <= low:
            hints.append(f"Body fat {latest_body_fat}% is lean: a lean bulk is a good fit if building muscle/strength is the goal.")
        else:
            hints.append(f"Body fat {latest_body_fat}% is in the middle: any phase works; pick based on your goal (or recomp).")
    else:
        missing = []
        if latest_body_fat is None:
            missing.append("log a body-fat estimate (Body Composition)")
        if sex not in ("male", "female"):
            missing.append("set your sex in the profile below")
        hints.append("For a more specific phase suggestion, " + " and ".join(missing) + ".")
    if profile.get("experience") == "beginner":
        hints.append("Newer lifters can often recomp (build muscle while slowly losing fat) at maintenance.")
    if balance["maintenance_kcal"] is None:
        hints.append("Log meals and weigh-ins for ~2 weeks (or fill in the profile) so calorie targets can be calculated.")
    return hints


def strength_trends_recent(today: date, days: int = 28) -> list[dict]:
    since = (today - timedelta(days=days)).isoformat()
    names = {
        s["exercise_name"]
        for session in database_v2.get_workout_sessions()
        if session["session_date"] >= since
        for s in session["sets"]
    }
    out = []
    for name in sorted(names):
        t = get_exercise_trend(name)
        if t.get("trend"):
            out.append({"exercise": name, "trend": t["trend"], "change_lb": t["change_lb"]})
    return out


def phase_overview(today: date | None = None) -> dict:
    today = today or date.today()
    balance = energy_balance(today)
    profile = get_profile()
    plan = get_active_plan()
    body = database_v2.get_body_entries(limit=200)
    latest_bf = next((b["body_fat"] for b in body if b["body_fat"] is not None), None)
    trends = strength_trends_recent(today)

    return {
        "profile": profile,
        "energy_balance": balance,
        "latest_body_fat": latest_bf,
        "active_plan": plan,
        "progress": plan_progress(plan, balance, trends, today) if plan else None,
        "hints": phase_hints(profile, latest_bf, balance),
        "phases": {k: {"label": v["label"], "rate_range": v["rate_range"], "default_rate": v["default_rate"]} for k, v in PHASES.items()},
    }
