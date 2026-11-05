"""
Import free-form training/meal notes (copy-pasted) into the log.

Flow:  split into days (code) -> read each day (local LLM, structured
JSON) -> clean up + check (code) -> you review/edit -> save (one
transaction, tagged with an import batch so it can be undone).

Rules:
- The model only extracts what's written. Numbers it estimates (meal
  calories/macros that weren't in the notes) are flagged as estimates.
- Every extracted item keeps the text it came from, and any line that
  didn't end up in an item is reported back as "not imported", so
  nothing disappears silently.
- Notes go only to the local model (src/local_llm.py).
"""

import json
import re
import sqlite3
import threading
import uuid
from datetime import date, datetime, timedelta

import src.database_v2 as database_v2
from src import local_llm

MAX_TEXT_CHARS = 150_000
MAX_BLOCK_CHARS = 4_000
KG_TO_LB = 2.20462

MEAL_TYPES = ["breakfast", "lunch", "dinner", "snack", "pre-workout", "post-workout"]
ACTIVITY_TYPES = ["running", "basketball", "conditioning", "sprint", "plyometric", "agility"]
BASKETBALL_KINDS = ["practice", "game", "skills", "pickup"]
RUN_KINDS = ["easy", "recovery", "long", "tempo", "intervals", "race"]
ACTIVITY_KINDS = BASKETBALL_KINDS + RUN_KINDS
KM_TO_MI = 0.621371

EXERCISE_ALIASES = {
    "bench": "Bench Press",
    "bench press": "Bench Press",
    "bp": "Bench Press",
    "squat": "Back Squat",
    "squats": "Back Squat",
    "back squat": "Back Squat",
    "deadlift": "Deadlift",
    "deadlifts": "Deadlift",
    "dl": "Deadlift",
    "rdl": "Romanian Deadlift",
    "rdls": "Romanian Deadlift",
    "ohp": "Overhead Press",
    "overhead press": "Overhead Press",
    "military press": "Overhead Press",
    "pullups": "Pull-up",
    "pull ups": "Pull-up",
    "pull-ups": "Pull-up",
    "chinups": "Chin-up",
    "chin ups": "Chin-up",
    "rows": "Barbell Row",
    "row": "Barbell Row",
}

# --------------------------------------------------
# 1. Split notes into day blocks (deterministic)
# --------------------------------------------------

_MONTHS = {
    m: i + 1
    for i, names in enumerate(
        [("jan", "january"), ("feb", "february"), ("mar", "march"), ("apr", "april"), ("may",),
         ("jun", "june"), ("jul", "july"), ("aug", "august"), ("sep", "sept", "september"),
         ("oct", "october"), ("nov", "november"), ("dec", "december")]
    )
    for m in names
}
_MONTH_RE = "|".join(sorted(_MONTHS, key=len, reverse=True))
_WEEKDAY = r"(?:(?:mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)[a-z]*\.?,?\s+)?"
_LEAD = r"^\s*(?:[#*>\-–—•]+\s*)?" + _WEEKDAY

_DATE_PATTERNS = [
    # 2026-10-03
    (re.compile(_LEAD + r"(\d{4})-(\d{1,2})-(\d{1,2})\b", re.I), "ymd"),
    # Oct 3 / October 3rd, 2026 / Oct. 3
    (re.compile(_LEAD + rf"({_MONTH_RE})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?\b(?:,?\s*(\d{{4}}))?", re.I), "mdy_name"),
    # 3 Oct / 3rd October 2026
    (re.compile(_LEAD + rf"(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MONTH_RE})\b\.?(?:,?\s*(\d{{4}}))?", re.I), "dmy_name"),
    # 10/3, 10/03/26, 10-3-2026 (US month/day)
    (re.compile(_LEAD + r"(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b", re.I), "mdy_num"),
]


def _infer_year(month: int, day: int, today: date) -> int | None:
    for year in (today.year, today.year - 1):
        try:
            if date(year, month, day) <= today:
                return year
        except ValueError:
            return None
    return today.year - 1


def detect_date(line: str, today: date) -> tuple[str | None, int]:
    """If `line` starts with a date, return (ISO date, end index of the date text)."""

    for pattern, kind in _DATE_PATTERNS:
        m = pattern.match(line)
        if not m:
            continue
        try:
            if kind == "ymd":
                y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            elif kind == "mdy_name":
                mo, d = _MONTHS[m.group(1).lower()], int(m.group(2))
                y = int(m.group(3)) if m.group(3) else _infer_year(mo, d, today)
            elif kind == "dmy_name":
                d, mo = int(m.group(1)), _MONTHS[m.group(2).lower()]
                y = int(m.group(3)) if m.group(3) else _infer_year(mo, d, today)
            else:
                mo, d = int(m.group(1)), int(m.group(2))
                if m.group(3):
                    y = int(m.group(3))
                    y = y + 2000 if y < 100 else y
                else:
                    y = _infer_year(mo, d, today)
            if y is None:
                continue
            parsed = date(y, mo, d)
        except (ValueError, KeyError):
            continue
        # A "date" followed directly by x/@ is more likely a set ("10/3 x 5"), skip it.
        rest = line[m.end():m.end() + 3].strip().lower()
        if rest.startswith(("x", "@", "lb", "kg")):
            continue
        if parsed > today:
            continue
        return parsed.isoformat(), m.end()

    return None, 0


def split_into_days(text: str, today: date | None = None) -> list[dict]:
    today = today or date.today()
    text = text.replace("\r\n", "\n")[:MAX_TEXT_CHARS]
    blocks: list[dict] = []
    current = {"date": None, "lines": []}

    for line in text.split("\n"):
        iso, _end = detect_date(line, today)
        if iso:
            if current["lines"] or current["date"]:
                blocks.append(current)
            current = {"date": iso, "lines": [line]}
        else:
            current["lines"].append(line)
    if current["lines"] or current["date"]:
        blocks.append(current)

    # Merge blocks for the same date; drop empty undated preamble.
    merged: dict[str | None, list[str]] = {}
    order: list[str | None] = []
    undated: list[list[str]] = []
    for b in blocks:
        if not any(l.strip() for l in b["lines"]):
            continue
        if b["date"] is None:
            undated.append(b["lines"])
            continue
        if b["date"] not in merged:
            merged[b["date"]] = []
            order.append(b["date"])
        merged[b["date"]] += b["lines"]

    result = [{"date": d, "text": "\n".join(merged[d]).strip()} for d in order]

    # Undated text (e.g. notes with no dates at all) keeps date=None; the
    # model may find a date inside it, otherwise you set it on review.
    for lines in undated:
        result.append({"date": None, "text": "\n".join(lines).strip()})

    # Very long single days get split so each LLM call stays small.
    final = []
    for b in result:
        if len(b["text"]) <= MAX_BLOCK_CHARS:
            final.append(b)
            continue
        part: list[str] = []
        for line in b["text"].split("\n"):
            if sum(len(p) + 1 for p in part) + len(line) > MAX_BLOCK_CHARS and part:
                final.append({"date": b["date"], "text": "\n".join(part)})
                part = []
            part.append(line)
        if part:
            final.append({"date": b["date"], "text": "\n".join(part)})

    return final


# --------------------------------------------------
# 2. Read one day with the local model
# --------------------------------------------------

_NUM = {"type": ["number", "null"]}
_STR = {"type": ["string", "null"]}

DAY_SCHEMA = {
    "type": "object",
    "properties": {
        "date": {"type": ["string", "null"], "description": "YYYY-MM-DD if the text states a date"},
        "meals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "meal_type": {"type": ["string", "null"], "enum": MEAL_TYPES + [None]},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "food": {"type": "string"},
                                "quantity": _NUM,
                                "unit": _STR,
                                "calories": _NUM,
                                "protein_g": _NUM,
                                "carbs_g": _NUM,
                                "fat_g": _NUM,
                                "source": {"type": "string"},
                            },
                            "required": ["food", "quantity", "unit", "calories", "protein_g", "carbs_g", "fat_g", "source"],
                        },
                    },
                },
                "required": ["meal_type", "items"],
            },
        },
        "workouts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": _STR,
                    "exercises": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "exercise": {"type": "string"},
                                "weight": _NUM,
                                "unit": {"type": ["string", "null"], "enum": ["lb", "kg", None]},
                                "reps": _NUM,
                                "sets": _NUM,
                                "rpe": _NUM,
                                "source": {"type": "string"},
                            },
                            "required": ["exercise", "weight", "unit", "reps", "sets", "rpe", "source"],
                        },
                    },
                },
                "required": ["name", "exercises"],
            },
        },
        "activities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ACTIVITY_TYPES},
                    "kind": {"type": ["string", "null"], "enum": ACTIVITY_KINDS + [None]},
                    "distance": _NUM,
                    "distance_unit": {"type": ["string", "null"], "enum": ["mi", "km", None]},
                    "minutes": _NUM,
                    "rpe": _NUM,
                    "source": {"type": "string"},
                },
                "required": ["type", "kind", "distance", "distance_unit", "minutes", "rpe", "source"],
            },
        },
        "body_weight": _NUM,
        "body_weight_unit": {"type": ["string", "null"], "enum": ["lb", "kg", None]},
        "sleep_hours": _NUM,
        "energy": _NUM,
        "soreness": _NUM,
        "pain": _NUM,
        "other_notes": {"type": ["string", "null"]},
    },
    "required": ["date", "meals", "workouts", "activities", "body_weight", "body_weight_unit", "sleep_hours",
                 "energy", "soreness", "pain", "other_notes"],
}

PARSE_PROMPT = """You convert one athlete's personal training and meal notes into JSON. Today is {today}.

Extract ONLY what is written. Never invent foods, exercises, sets or numbers.
- meals: group foods by meal (breakfast/lunch/dinner/snack/pre-workout/post-workout, or null if not said).
  One item per food. Keep the details that matter for nutrition in the food name, e.g.
  "whey protein shake (2 scoops, with milk)", "coffee with milk", "chicken burrito bowl".
  quantity + unit as written (e.g. 3 + "eggs", 200 + "g", 1 + "cup"); null if not given.
  calories/protein_g/carbs_g/fat_g ONLY if the notes state them for that food; otherwise null.
  If the notes give one calorie number for a whole meal, put it on the first item of that meal.
- workouts: normally ONE workout per day containing all exercises; name it as the notes do
  ("Push day", "Legs") or null. One exercise row per distinct weight x reps x RPE scheme.
  Common shorthand: "155x5x3" or "3x5 @155" = 3 sets of 5 reps at 155; "5,5,4 @ 155" = three rows/sets
  (use separate rows when reps differ); "@8" or "rpe 8" = RPE 8. "bw" = bodyweight (weight null).
  If an RPE applies to only some sets ("5x5, last set rpe 9"), split into rows: 4 sets with rpe null
  and 1 set with rpe 9.
  Use these exercise names when they match: {exercises}.
- activities: anything that isn't weightlifting: runs, basketball, conditioning (bike, rower, swim,
  hike), sprints, plyometrics, agility. type = running | basketball | conditioning | sprint | plyometric
  | agility. kind: for basketball practice | game | skills | pickup; for runs easy | recovery | long |
  tempo | intervals | race (null if not said). distance + distance_unit (mi or km) and minutes only if
  written ("3 mi in 27:30" = 3 mi, 27.5 minutes; "1.5 hrs" = 90). rpe only if written (0-10;
  "felt like a 7" = 7). Never put runs or basketball in workouts.
- body_weight ("bw 201" next to a date or "weighed 201" = body weight), sleep_hours, energy (0-10),
  soreness (0-10), pain (0-10): only if written. Any ache/pain rating (e.g. "knee achy 3/10") goes in
  pain; mention where in other_notes.
- source: copy the exact short piece of the notes each item came from.
- other_notes: anything else worth keeping (how it felt, etc.), briefly; null if nothing.
- date: YYYY-MM-DD only if the text itself states the date ("yesterday" = {yesterday}, "today" =
  {today}); else null."""


def parse_block(block: dict, model: str, known_exercises: list[str], today: date) -> dict:
    exercises = ", ".join(known_exercises[:80]) or "none yet"
    messages = [
        {"role": "system", "content": PARSE_PROMPT.format(
            today=today.isoformat(), yesterday=(today - timedelta(days=1)).isoformat(), exercises=exercises)},
        {"role": "user", "content": block["text"]},
    ]
    response = local_llm.chat(
        model, messages, format=DAY_SCHEMA, think="low", options={"temperature": 0, "num_predict": 4096}
    )
    try:
        return json.loads(response.message.content)
    except (json.JSONDecodeError, TypeError):
        return {"_error": "The model's answer for this day wasn't readable."}


ESTIMATE_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "calories": {"type": "number"},
                    "protein_g": {"type": "number"},
                    "carbs_g": {"type": "number"},
                    "fat_g": {"type": "number"},
                },
                "required": ["index", "calories", "protein_g", "carbs_g", "fat_g"],
            },
        }
    },
    "required": ["items"],
}

ESTIMATE_PROMPT = """Estimate nutrition for each food at the stated amount, using typical
values (USDA-style). If the amount is missing, assume one typical serving. Return one row per
index. These are estimates for a training log; be realistic, not precise-sounding."""


def estimate_macros(items: list[dict], model: str) -> dict[int, dict]:
    if not items:
        return {}
    listing = "\n".join(
        f"{i}: {it['food_name']} — {it['quantity'] if it['quantity'] is not None else '?'} {it['serving_unit'] or ''}".strip()
        for i, it in enumerate(items)
    )
    response = local_llm.chat(
        model,
        [{"role": "system", "content": ESTIMATE_PROMPT}, {"role": "user", "content": listing}],
        format=ESTIMATE_SCHEMA,
        think="low",
        options={"temperature": 0},
    )
    try:
        rows = json.loads(response.message.content)["items"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return {}
    return {
        r["index"]: r
        for r in rows
        if isinstance(r, dict) and isinstance(r.get("index"), int) and 0 <= r["index"] < len(items)
    }


# --------------------------------------------------
# 3. Clean up and check (deterministic)
# --------------------------------------------------

def _num(value, lo=None, hi=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if lo is not None and value < lo:
        return None
    if hi is not None and value > hi:
        return None
    return round(float(value), 2)


def canonical_exercise(name: str, known: list[str]) -> str:
    clean = re.sub(r"\s+", " ", name.strip())
    lower = clean.lower()
    for k in known:
        if k.lower() == lower:
            return k
    alias = EXERCISE_ALIASES.get(lower)
    if alias:
        for k in known:
            if k.lower() == alias.lower():
                return k
        return alias
    return clean[:1].upper() + clean[1:] if clean else clean


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def uncovered_lines(block_text: str, sources: list[str], header_end: int = 0) -> list[str]:
    """Lines of the notes that no extracted item points back to."""

    source_tokens = [_tokens(s) for s in sources if s and s.strip()]
    missing = []
    for i, line in enumerate(block_text.split("\n")):
        text = line[header_end:] if i == 0 else line
        tokens = _tokens(text)
        if len(tokens) < 2:
            continue
        covered = any(len(tokens & st) >= max(1, min(len(tokens), len(st)) * 0.5) for st in source_tokens)
        if not covered:
            missing.append(line.strip())
    return missing


def normalize_day(raw: dict, block: dict, known_exercises: list[str], foods: list[dict], today: date) -> dict:
    warnings: list[str] = []
    if raw.get("_error"):
        warnings.append(raw["_error"])

    # Date: the date found by code wins; otherwise accept a valid one from the model.
    day_date = block["date"]
    if not day_date and isinstance(raw.get("date"), str):
        try:
            candidate = date.fromisoformat(raw["date"][:10])
            if candidate <= today:
                day_date = candidate.isoformat()
        except ValueError:
            pass
    if not day_date:
        warnings.append("No date found. Set the date before saving.")

    foods_by_name = {f["name"].lower(): f for f in foods}
    sources: list[str] = []

    meals = []
    for meal in raw.get("meals") or []:
        meal_type = meal.get("meal_type") if meal.get("meal_type") in MEAL_TYPES else None
        items = []
        for it in meal.get("items") or []:
            name = (it.get("food") or "").strip()
            if not name:
                continue
            sources.append(it.get("source") or name)
            qty = _num(it.get("quantity"), 0, 10_000)
            item = {
                "food_name": name[:120],
                "quantity": qty,
                "serving_unit": (it.get("unit") or None),
                "calories": _num(it.get("calories"), 0, 10_000),
                "protein_g": _num(it.get("protein_g"), 0, 1_000),
                "carbs_g": _num(it.get("carbs_g"), 0, 2_000),
                "fat_g": _num(it.get("fat_g"), 0, 1_000),
                "is_estimate": False,
                "macro_source": "notes",
                "source": (it.get("source") or "")[:200],
            }
            if item["calories"] is None:
                saved = foods_by_name.get(name.lower())
                if saved and saved.get("calories") is not None:
                    servings = qty if qty and (not item["serving_unit"] or (saved.get("serving_unit") or "").lower().rstrip("s") == item["serving_unit"].lower().rstrip("s")) else 1
                    for key in ("calories", "protein_g", "carbs_g", "fat_g"):
                        if saved.get(key) is not None:
                            item[key] = round(saved[key] * servings, 1)
                    item["macro_source"] = "my_foods"
                    item["is_estimate"] = bool(saved.get("is_estimate"))
                else:
                    item["macro_source"] = "none"
            items.append(item)
        if items:
            meals.append({"meal_type": meal_type, "items": items})

    workouts = []
    for w in raw.get("workouts") or []:
        exercises = []
        for ex in w.get("exercises") or []:
            name = (ex.get("exercise") or "").strip()
            if not name:
                continue
            sources.append(ex.get("source") or name)
            weight = _num(ex.get("weight"), 0, 2_000)
            if weight is not None and (ex.get("unit") or "").lower() == "kg":
                weight = round(weight * KG_TO_LB, 1)
            reps = _num(ex.get("reps"), 1, 200)
            sets = _num(ex.get("sets"), 1, 30)
            if reps is None:
                warnings.append(f"{name}: no reps found — check this row.")
            exercises.append(
                {
                    "exercise": canonical_exercise(name, known_exercises),
                    "weight": weight,
                    "reps": int(reps) if reps else None,
                    "sets": int(sets) if sets else 1,
                    "rpe": _num(ex.get("rpe"), 1, 10),
                    "source": (ex.get("source") or "")[:200],
                }
            )
        if exercises:
            workouts.append({"name": (w.get("name") or None), "exercises": exercises})

    # One session per day: the model sometimes splits exercises into separate "workouts".
    if len(workouts) > 1:
        names = [w["name"] for w in workouts if w["name"]]
        exercise_names = {e["exercise"].lower() for w in workouts for e in w["exercises"]}
        session_name = next((n for n in names if n.lower() not in exercise_names), None)
        workouts = [{"name": session_name, "exercises": [e for w in workouts for e in w["exercises"]]}]
    elif workouts and workouts[0]["name"] and workouts[0]["name"].lower() in {e["exercise"].lower() for e in workouts[0]["exercises"]}:
        workouts[0]["name"] = None

    activities = []
    for a in raw.get("activities") or []:
        kind = a.get("type")
        if kind not in ACTIVITY_TYPES:
            continue
        sources.append(a.get("source") or kind)
        distance = _num(a.get("distance"), 0, 200)
        if distance is not None and (a.get("distance_unit") or "").lower() == "km":
            distance = round(distance * KM_TO_MI, 2)
        sub = a.get("kind")
        activities.append(
            {
                "session_type": kind,
                "subtype": sub if kind == "basketball" and sub in BASKETBALL_KINDS else ("practice" if kind == "basketball" else None),
                "run_type": sub if kind == "running" and sub in RUN_KINDS else None,
                "distance_miles": distance if kind in ("running", "conditioning") else None,
                "duration_minutes": _num(a.get("minutes"), 1, 1_440),
                "rpe": _num(a.get("rpe"), 0, 10),
                "source": (a.get("source") or "")[:200],
            }
        )
        if kind == "basketball" and activities[-1]["duration_minutes"] is None:
            warnings.append("Basketball: add the minutes so its load can be counted.")

    body_weight = _num(raw.get("body_weight"), 50, 1_000)
    if body_weight and (raw.get("body_weight_unit") or "").lower() == "kg":
        body_weight = round(body_weight * KG_TO_LB, 1)

    recovery = {
        "sleep_hours": _num(raw.get("sleep_hours"), 0, 24),
        "energy": _num(raw.get("energy"), 0, 10),
        "soreness": _num(raw.get("soreness"), 0, 10),
        "pain": _num(raw.get("pain"), 0, 10),
    }
    has_recovery = any(v is not None for v in recovery.values())
    other_notes = (raw.get("other_notes") or None)
    if other_notes:
        sources.append(other_notes)
    for key in ("sleep_hours", "energy", "soreness", "pain", "body_weight"):
        if raw.get(key) is not None:
            sources.append(f"{key.replace('_', ' ')} {raw.get(key)}")

    _, header_end = detect_date(block["text"].split("\n")[0], today)

    return {
        "date": day_date,
        "include": True,
        "meals": meals,
        "workouts": workouts,
        "activities": activities,
        "body_weight": body_weight,
        "recovery": recovery if has_recovery else None,
        "notes": other_notes,
        "warnings": warnings,
        "not_imported": uncovered_lines(block["text"], sources, header_end),
        "original_text": block["text"],
    }


def mark_existing(days: list[dict]) -> None:
    """Flag days that already have entries, and default those parts off."""

    conn = sqlite3.connect(database_v2.DB_PATH)
    for d in days:
        if not d["date"]:
            d["existing"] = {}
            continue
        q = lambda sql: conn.execute(sql, (d["date"],)).fetchone()[0]  # noqa: E731
        d["existing"] = {
            "meals": q("SELECT COUNT(*) FROM meals WHERE meal_date = ?") + q("SELECT COUNT(*) FROM nutrition WHERE nutrition_date = ?"),
            "workouts": q("SELECT COUNT(*) FROM workout_sessions WHERE session_date = ?") + q("SELECT COUNT(*) FROM workouts WHERE workout_date = ?"),
            "recovery": q("SELECT COUNT(*) FROM recovery WHERE recovery_date = ?"),
            "body": q("SELECT COUNT(*) FROM body_metrics WHERE metric_date = ?"),
            "activities": q("SELECT COUNT(*) FROM athletic_sessions WHERE session_date = ?")
            + q("SELECT COUNT(*) FROM running WHERE run_date = ?"),
        }
    conn.close()


def merge_same_date(days: list[dict]) -> list[dict]:
    """Combine blocks that ended up on the same date (long days split for the model)."""
    out: list[dict] = []
    by_date: dict[str, dict] = {}
    for d in days:
        if d["date"] and d["date"] in by_date:
            t = by_date[d["date"]]
            t["meals"] += d["meals"]
            t["workouts"] += d["workouts"]
            t["activities"] += d["activities"]
            t["body_weight"] = t["body_weight"] or d["body_weight"]
            t["recovery"] = t["recovery"] or d["recovery"]
            t["notes"] = "; ".join(n for n in (t["notes"], d["notes"]) if n) or None
            t["warnings"] += d["warnings"]
            t["not_imported"] += d["not_imported"]
            t["original_text"] += "\n" + d["original_text"]
        else:
            out.append(d)
            if d["date"]:
                by_date[d["date"]] = d
    return sorted(out, key=lambda d: d["date"] or "9999")


# --------------------------------------------------
# 4. Background job (parsing a month takes a few minutes)
# --------------------------------------------------

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def start_parse_job(text: str, model: str, today: date | None = None) -> str:
    if not text or not text.strip():
        raise ValueError("Paste some notes first.")
    if len(text) > MAX_TEXT_CHARS:
        raise ValueError(f"That's more than {MAX_TEXT_CHARS:,} characters. Import it in smaller pieces.")
    local_llm.check_model(model)  # fail fast if Ollama/model isn't ready

    job_id = uuid.uuid4().hex
    blocks = split_into_days(text, today)
    with _jobs_lock:
        _jobs[job_id] = {"status": "running", "done": 0, "total": len(blocks), "days": None, "error": None}

    thread = threading.Thread(target=_run_job, args=(job_id, blocks, model, today or date.today()), daemon=True)
    thread.start()
    return job_id


def _run_job(job_id: str, blocks: list[dict], model: str, today: date) -> None:
    known = database_v2.get_exercise_names()
    foods = database_v2.search_foods("", limit=1000)
    days = []
    try:
        for block in blocks:
            raw = parse_block(block, model, known, today)
            day = normalize_day(raw, block, known, foods, today)

            missing = [it for m in day["meals"] for it in m["items"] if it["calories"] is None]
            for i, est in estimate_macros(missing, model).items():
                for key in ("calories", "protein_g", "carbs_g", "fat_g"):
                    missing[i][key] = round(float(est[key]), 1)
                missing[i]["is_estimate"] = True
                missing[i]["macro_source"] = "estimate"

            days.append(day)
            with _jobs_lock:
                _jobs[job_id]["done"] += 1

        days = merge_same_date(days)
        mark_existing(days)
        for d in days:
            ex = d.get("existing") or {}
            d["include_meals"] = not ex.get("meals")
            d["include_workouts"] = not ex.get("workouts")
            d["include_recovery"] = not ex.get("recovery")
            d["include_body"] = not ex.get("body")
            d["include_activities"] = not ex.get("activities")

        with _jobs_lock:
            _jobs[job_id].update(status="done", days=days)
    except local_llm.LocalLLMError as exc:
        with _jobs_lock:
            _jobs[job_id].update(status="failed", error=str(exc))
    except Exception as exc:  # report, don't crash the server thread
        with _jobs_lock:
            _jobs[job_id].update(status="failed", error=f"Import failed: {type(exc).__name__}")


def get_job(job_id: str) -> dict | None:
    with _jobs_lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


# --------------------------------------------------
# 5. Save (one transaction) and undo
# --------------------------------------------------

def commit_days(days: list[dict], source: str = "notes") -> dict:
    """
    `days` come back from the review screen (already validated by the
    API schema). Everything is written in ONE transaction, tagged with
    a new import batch id.
    """

    conn = sqlite3.connect(database_v2.DB_PATH)
    counts = {"days": 0, "meals": 0, "workout_sessions": 0, "activities": 0, "recovery_entries": 0, "body_entries": 0}
    try:
        with conn:
            batch_id = conn.execute("INSERT INTO import_batches (days, source) VALUES (0, ?)", (source,)).lastrowid
            for d in days:
                when = d["date"]
                wrote = False
                for meal in d.get("meals", []):
                    meal_id = conn.execute(
                        "INSERT INTO meals (meal_date, meal_type, notes, import_batch_id) VALUES (?, ?, ?, ?)",
                        (when, meal["meal_type"], "Imported from notes", batch_id),
                    ).lastrowid
                    for it in meal["items"]:
                        conn.execute(
                            """
                            INSERT INTO meal_items (meal_id, food_name, quantity, serving_unit, calories,
                                                    protein_g, carbs_g, fat_g, is_estimate)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (meal_id, it["food_name"], it["quantity"] or 1, it["serving_unit"], it["calories"],
                             it["protein_g"], it["carbs_g"], it["fat_g"], 1 if it["is_estimate"] else 0),
                        )
                    counts["meals"] += 1
                    wrote = True
                for w in d.get("workouts", []):
                    session_id = conn.execute(
                        "INSERT INTO workout_sessions (session_date, name, notes, import_batch_id) VALUES (?, ?, ?, ?)",
                        (when, w["name"], d.get("notes"), batch_id),
                    ).lastrowid
                    numbers: dict[str, int] = {}
                    for ex in w["exercises"]:
                        for _ in range(ex["sets"]):
                            numbers[ex["exercise"]] = numbers.get(ex["exercise"], 0) + 1
                            conn.execute(
                                """
                                INSERT INTO workout_sets (session_id, exercise_name, set_number, reps, weight, rpe, is_completed)
                                VALUES (?, ?, ?, ?, ?, ?, 1)
                                """,
                                (session_id, ex["exercise"], numbers[ex["exercise"]], ex["reps"], ex["weight"], ex["rpe"]),
                            )
                    counts["workout_sessions"] += 1
                    wrote = True
                for a in d.get("activities", []):
                    distance, minutes = a.get("distance_miles"), a.get("duration_minutes")
                    pace = round(minutes / distance, 2) if a["session_type"] == "running" and distance and minutes else None
                    conn.execute(
                        """
                        INSERT INTO athletic_sessions (session_date, session_type, subtype, run_type, distance_miles,
                            duration_minutes, pace_per_mile, rpe, notes, import_batch_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (when, a["session_type"], a.get("subtype"), a.get("run_type"), distance, minutes, pace,
                         a.get("rpe"), a.get("notes"), batch_id),
                    )
                    counts["activities"] += 1
                    wrote = True
                if d.get("recovery"):
                    # Merge with what's already logged for that day: a new row carries the
                    # old values forward plus the new ones. The newest row is the one used,
                    # and Undo deletes it, which restores the original.
                    prev = conn.execute(
                        "SELECT sleep_hours, energy, soreness, pain FROM recovery WHERE recovery_date = ? ORDER BY id DESC LIMIT 1",
                        (when,),
                    ).fetchone()
                    r = dict(d["recovery"])
                    if prev:
                        for key, old in zip(("sleep_hours", "energy", "soreness", "pain"), prev):
                            if r.get(key) is None:
                                r[key] = old
                    conn.execute(
                        """
                        INSERT INTO recovery (recovery_date, sleep_hours, energy, soreness, pain, notes, import_batch_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (when, r["sleep_hours"], r["energy"], r["soreness"], r["pain"], "Imported from notes", batch_id),
                    )
                    counts["recovery_entries"] += 1
                    wrote = True
                if d.get("body_weight"):
                    prev = conn.execute(
                        "SELECT body_fat, waist FROM body_metrics WHERE metric_date = ? ORDER BY id DESC LIMIT 1", (when,)
                    ).fetchone()
                    conn.execute(
                        "INSERT INTO body_metrics (metric_date, body_weight, body_fat, waist, notes, import_batch_id) VALUES (?, ?, ?, ?, ?, ?)",
                        (when, d["body_weight"], prev[0] if prev else None, prev[1] if prev else None, "Imported from notes", batch_id),
                    )
                    counts["body_entries"] += 1
                    wrote = True
                counts["days"] += 1 if wrote else 0

            conn.execute(
                """
                UPDATE import_batches SET days = ?, meals = ?, workout_sessions = ?, activities = ?,
                    recovery_entries = ?, body_entries = ? WHERE id = ?
                """,
                (counts["days"], counts["meals"], counts["workout_sessions"], counts["activities"],
                 counts["recovery_entries"], counts["body_entries"], batch_id),
            )
    finally:
        conn.close()

    return {"batch_id": batch_id, **counts}


def list_batches() -> list[dict]:
    conn = sqlite3.connect(database_v2.DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("SELECT * FROM import_batches ORDER BY id DESC LIMIT 20")]
    conn.close()
    return rows


def undo_batch(batch_id: int) -> bool:
    conn = sqlite3.connect(database_v2.DB_PATH)
    try:
        with conn:
            row = conn.execute("SELECT undone_at FROM import_batches WHERE id = ?", (batch_id,)).fetchone()
            if row is None or row[0] is not None:
                return False
            conn.execute(
                "DELETE FROM meal_items WHERE meal_id IN (SELECT id FROM meals WHERE import_batch_id = ?)", (batch_id,)
            )
            conn.execute("DELETE FROM meals WHERE import_batch_id = ?", (batch_id,))
            conn.execute(
                "DELETE FROM workout_sets WHERE session_id IN (SELECT id FROM workout_sessions WHERE import_batch_id = ?)",
                (batch_id,),
            )
            conn.execute("DELETE FROM workout_sessions WHERE import_batch_id = ?", (batch_id,))
            conn.execute("DELETE FROM recovery WHERE import_batch_id = ?", (batch_id,))
            conn.execute("DELETE FROM athletic_sessions WHERE import_batch_id = ?", (batch_id,))
            conn.execute("DELETE FROM body_metrics WHERE import_batch_id = ?", (batch_id,))
            conn.execute(
                "UPDATE import_batches SET undone_at = ? WHERE id = ?",
                (datetime.now().isoformat(timespec="seconds"), batch_id),
            )
    finally:
        conn.close()
    return True


def parse_quick(text: str, model: str, today: date | None = None) -> dict:
    """
    Read one quick log message ("lunch: burrito bowl ~800 cal, benched
    155x5x3 @8, 90 min practice"). Defaults to today unless the message
    names another day. Returns one day for review; nothing is saved.
    """
    today = today or date.today()
    text = (text or "").strip()
    if not text:
        raise ValueError("Tell the coach what you ate or did.")
    if len(text) > MAX_BLOCK_CHARS:
        raise ValueError("That's long for a quick log. Use Import Notes for big pastes.")

    block_date, _ = detect_date(text.split("\n")[0], today)
    block = {"date": block_date, "text": text}
    known = database_v2.get_exercise_names()
    foods = database_v2.search_foods("", limit=1000)

    raw = parse_block(block, model, known, today)
    day = normalize_day(raw, block, known, foods, today)
    if not day["date"]:
        day["date"] = today.isoformat()
        day["warnings"] = [w for w in day["warnings"] if not w.startswith("No date found")]

    missing = [it for m in day["meals"] for it in m["items"] if it["calories"] is None]
    for i, est in estimate_macros(missing, model).items():
        for key in ("calories", "protein_g", "carbs_g", "fat_g"):
            missing[i][key] = round(float(est[key]), 1)
        missing[i]["is_estimate"] = True
        missing[i]["macro_source"] = "estimate"

    # A quick log is new information for that day, so everything starts ticked.
    mark_existing([day])
    day.update(include_meals=True, include_workouts=True, include_activities=True,
               include_recovery=True, include_body=True)
    return day
