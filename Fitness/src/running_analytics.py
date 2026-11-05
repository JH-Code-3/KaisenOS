"""
Running & athleticism analysis — all math, no LLM.

Combines the athletic_sessions table (runs, sprints, plyometrics,
agility, conditioning) with legacy runs logged by the CLI coach.
"""

from datetime import date, timedelta
from statistics import mean

from src.database_v2 import get_athletic_sessions, get_legacy_runs

SESSION_TYPES = ["running", "sprint", "plyometric", "agility", "conditioning", "basketball"]
BASKETBALL_TYPES = ["practice", "game", "skills", "pickup"]
ACWR_HIGH = 1.5   # this week's load vs. your 4-week average: above this is a spike
ACWR_LOW = 0.8    # below this, fitness may be slipping (or it's a planned deload)
RUN_TYPES = ["easy", "recovery", "long", "tempo", "intervals", "race"]
EASY_TYPES = {"easy", "recovery", "long"}
HARD_TYPES = {"tempo", "intervals", "race"}
EASY_RPE_MAX = 5           # untyped runs at or below this RPE count as easy
HARD_RPE_MIN = 7           # ...at or above this count as hard
EASY_SHARE_TARGET = 80     # % of running miles at easy effort (80/20 guideline)
RIEGEL_EXPONENT = 1.06
FIVE_K_MILES = 3.10686


def pace(distance_miles, duration_minutes):
    if not distance_miles or not duration_minutes or distance_miles <= 0 or duration_minutes <= 0:
        return None
    return round(duration_minutes / distance_miles, 2)


def format_pace(minutes):
    if minutes is None:
        return None
    total = round(minutes * 60)
    return f"{total // 60}:{total % 60:02d}"


def format_duration(minutes):
    if minutes is None:
        return None
    total = round(minutes * 60)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def all_sessions() -> list[dict]:
    """Every session, newest first, with pace filled in where possible."""

    sessions = []
    for s in get_athletic_sessions():
        sessions.append({**s, "source": "log", "pace_per_mile": pace(s["distance_miles"], s["duration_minutes"]) or s["pace_per_mile"]})
    for r in get_legacy_runs():
        sessions.append(
            {
                "id": r["id"],
                "session_date": r["run_date"],
                "session_type": "running",
                "subtype": None,
                "run_type": None,
                "distance_miles": r["distance_miles"],
                "duration_minutes": r["duration_minutes"],
                "pace_per_mile": pace(r["distance_miles"], r["duration_minutes"]) or r["pace_per_mile"],
                "sprint_distance_yards": None,
                "sprint_time_seconds": None,
                "jump_height_inches": None,
                "reps": None,
                "rpe": r["rpe"],
                "notes": r["notes"],
                "source": "legacy",
            }
        )
    return sorted(sessions, key=lambda s: (s["session_date"], s["id"] or 0), reverse=True)


def effort(session) -> str:
    """easy | hard | unknown, from the run type or RPE."""
    if session.get("run_type") in EASY_TYPES:
        return "easy"
    if session.get("run_type") in HARD_TYPES:
        return "hard"
    rpe = session.get("rpe")
    if rpe is not None:
        if rpe <= EASY_RPE_MAX:
            return "easy"
        if rpe >= HARD_RPE_MIN:
            return "hard"
        return "moderate"
    return "unknown"


def weekly_mileage(sessions, today: date, weeks: int = 8) -> list[dict]:
    """Running miles per calendar week (Mon–Sun), oldest first."""
    this_monday = today - timedelta(days=today.weekday())
    out = []
    for i in range(weeks - 1, -1, -1):
        start = this_monday - timedelta(weeks=i)
        end = start + timedelta(days=6)
        runs = [
            s for s in sessions
            if s["session_type"] == "running" and start.isoformat() <= s["session_date"] <= end.isoformat()
        ]
        out.append(
            {
                "week_start": start.isoformat(),
                "miles": round(sum(s["distance_miles"] or 0 for s in runs), 2),
                "runs": len(runs),
                "long_run": max((s["distance_miles"] or 0 for s in runs), default=0),
            }
        )
    return out


def intensity_split(sessions, today: date, days: int = 28) -> dict:
    since = (today - timedelta(days=days - 1)).isoformat()
    miles = {"easy": 0.0, "moderate": 0.0, "hard": 0.0, "unknown": 0.0}
    for s in sessions:
        if s["session_type"] == "running" and s["session_date"] >= since and s["distance_miles"]:
            miles[effort(s)] += s["distance_miles"]
    known = miles["easy"] + miles["moderate"] + miles["hard"]
    easy_share = round(miles["easy"] / known * 100) if known else None
    return {
        "window_days": days,
        "miles": {k: round(v, 1) for k, v in miles.items()},
        "easy_share_pct": easy_share,
        "target_easy_pct": EASY_SHARE_TARGET,
        "status": None if easy_share is None else ("ok" if easy_share >= EASY_SHARE_TARGET - 10 else "too_hard"),
    }


def personal_bests(sessions) -> dict:
    runs = [s for s in sessions if s["session_type"] == "running" and s["pace_per_mile"] and (s["distance_miles"] or 0) >= 1]
    fastest = min(runs, key=lambda s: s["pace_per_mile"], default=None)
    longest = max(
        (s for s in sessions if s["session_type"] == "running" and s["distance_miles"]),
        key=lambda s: s["distance_miles"],
        default=None,
    )

    sprints: dict[float, dict] = {}
    for s in sessions:
        if s["session_type"] == "sprint" and s["sprint_distance_yards"] and s["sprint_time_seconds"]:
            best = sprints.get(s["sprint_distance_yards"])
            if best is None or s["sprint_time_seconds"] < best["time_seconds"]:
                sprints[s["sprint_distance_yards"]] = {
                    "distance_yards": s["sprint_distance_yards"],
                    "time_seconds": s["sprint_time_seconds"],
                    "date": s["session_date"],
                }

    jumps = [s for s in sessions if s["jump_height_inches"]]
    best_jump = max(jumps, key=lambda s: s["jump_height_inches"], default=None)

    return {
        "fastest_pace": (
            {"pace": fastest["pace_per_mile"], "pace_label": format_pace(fastest["pace_per_mile"]),
             "distance_miles": fastest["distance_miles"], "date": fastest["session_date"]}
            if fastest else None
        ),
        "longest_run": (
            {"distance_miles": longest["distance_miles"], "date": longest["session_date"]} if longest else None
        ),
        "sprints": sorted(sprints.values(), key=lambda s: s["distance_yards"]),
        "best_jump": (
            {"inches": best_jump["jump_height_inches"], "date": best_jump["session_date"]} if best_jump else None
        ),
    }


def five_k_estimate(sessions, today: date, days: int = 90) -> dict | None:
    """Riegel formula from your best recent run of 2+ miles. An estimate, not a prediction."""
    since = (today - timedelta(days=days)).isoformat()
    candidates = [
        s for s in sessions
        if s["session_type"] == "running" and s["session_date"] >= since
        and (s["distance_miles"] or 0) >= 2 and s["duration_minutes"]
    ]
    if not candidates:
        return None
    # The effort that projects to the fastest 5K.
    best = min(candidates, key=lambda s: s["duration_minutes"] * (FIVE_K_MILES / s["distance_miles"]) ** RIEGEL_EXPONENT)
    minutes = best["duration_minutes"] * (FIVE_K_MILES / best["distance_miles"]) ** RIEGEL_EXPONENT
    return {
        "minutes": round(minutes, 2),
        "label": format_duration(minutes),
        "based_on": {"date": best["session_date"], "distance_miles": best["distance_miles"],
                     "duration": format_duration(best["duration_minutes"])},
    }


def session_load(s) -> float | None:
    """Session RPE load: effort (RPE 0-10) x minutes."""
    if s.get("rpe") is None or not s.get("duration_minutes"):
        return None
    return round(s["rpe"] * s["duration_minutes"])


def load_summary(sessions, today: date, weeks: int = 8) -> dict:
    """
    Weekly session-RPE load (Mon-Sun), split into basketball vs. other
    conditioning, and the acute:chronic ratio (last 7 days vs. the
    average week of the last 28 days).
    """

    this_monday = today - timedelta(days=today.weekday())
    weekly = []
    for i in range(weeks - 1, -1, -1):
        start = this_monday - timedelta(weeks=i)
        end = start + timedelta(days=6)
        in_week = [s for s in sessions if start.isoformat() <= s["session_date"] <= end.isoformat()]
        bball = sum(session_load(s) or 0 for s in in_week if s["session_type"] == "basketball")
        other = sum(session_load(s) or 0 for s in in_week if s["session_type"] != "basketball")
        weekly.append({
            "week_start": start.isoformat(),
            "basketball": bball,
            "other": other,
            "basketball_sessions": sum(1 for s in in_week if s["session_type"] == "basketball"),
            "basketball_minutes": round(sum(s["duration_minutes"] or 0 for s in in_week if s["session_type"] == "basketball")),
        })

    def total(first: date, last: date) -> float:
        return sum(session_load(s) or 0 for s in sessions if first.isoformat() <= s["session_date"] <= last.isoformat())

    acute = total(today - timedelta(days=6), today)
    chronic_weekly = total(today - timedelta(days=27), today) / 4
    ratio = round(acute / chronic_weekly, 2) if chronic_weekly else None
    status = None
    if ratio is not None:
        status = "spike" if ratio > ACWR_HIGH else "low" if ratio < ACWR_LOW else "ok"

    unrated = sum(
        1 for s in sessions
        if s["session_date"] >= (today - timedelta(days=27)).isoformat()
        and s["session_type"] in ("basketball", "running", "conditioning")
        and session_load(s) is None
    )

    return {
        "weekly": weekly,
        "acute_7d": round(acute),
        "chronic_weekly_avg": round(chronic_weekly),
        "acwr": ratio,
        "status": status,
        "unrated_sessions_28d": unrated,
    }


def summary(today: date | None = None) -> dict:
    today = today or date.today()
    sessions = all_sessions()
    since = (today - timedelta(days=27)).isoformat()
    recent = [s for s in sessions if s["session_date"] >= since]

    pace_points = [
        {"date": s["session_date"], "pace": s["pace_per_mile"], "distance_miles": s["distance_miles"], "effort": effort(s)}
        for s in sessions
        if s["session_type"] == "running" and s["pace_per_mile"]
    ][:60][::-1]

    by_type = {t: sum(1 for s in recent if s["session_type"] == t) for t in SESSION_TYPES}

    return {
        "today": today.isoformat(),
        "weekly_mileage": weekly_mileage(sessions, today),
        "intensity_split": intensity_split(sessions, today),
        "bests": personal_bests(sessions),
        "five_k_estimate": five_k_estimate(sessions, today),
        "pace_points": pace_points,
        "sessions_last_28d": by_type,
        "load": load_summary(sessions, today),
        "avg_easy_pace_28d": format_pace(
            mean(s["pace_per_mile"] for s in recent if s["session_type"] == "running" and s["pace_per_mile"] and effort(s) == "easy")
        ) if any(s["session_type"] == "running" and s["pace_per_mile"] and effort(s) == "easy" for s in recent) else None,
    }
