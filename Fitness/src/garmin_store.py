"""
Local store for Garmin data: data/garmin_data.sqlite.

Kept completely separate from the workout log (data/athlete.db):
- garmin_sync.py is the only writer.
- The coach only reads from it.
- Nothing here imports or touches the workout database.

Tables
- sync_runs:      one row per manual sync (when, range, outcome). Never
                  stores the API key or access token.
- raw_responses:  Garmin's JSON exactly as returned, per endpoint and
                  date range. Re-syncing a range replaces it.
- daily_recovery: one row per date with the recovery numbers the coach
                  uses. Filled from raw_responses by `extract_daily_recovery`
                  once Garmin's field names are confirmed (see FIELD_MAP).
"""

import json
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
from src.paths import DATA_DIR  # noqa: E402

GARMIN_DB_PATH = DATA_DIR / "garmin_data.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sync_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    range_start TEXT NOT NULL,
    range_end TEXT NOT NULL,
    status TEXT NOT NULL,          -- running | ok | partial | failed
    endpoints_ok INTEGER DEFAULT 0,
    endpoints_failed INTEGER DEFAULT 0,
    error TEXT                     -- human-readable; never contains secrets
);

CREATE TABLE IF NOT EXISTS raw_responses (
    endpoint TEXT NOT NULL,        -- short name, e.g. "sleep_summaries"
    range_start TEXT NOT NULL,
    range_end TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    payload TEXT NOT NULL,         -- JSON as returned by Garmin
    PRIMARY KEY (endpoint, range_start, range_end)
);

CREATE TABLE IF NOT EXISTS daily_recovery (
    date TEXT PRIMARY KEY,
    sleep_seconds REAL,
    sleep_score REAL,
    hrv_overnight_avg REAL,
    hrv_status TEXT,
    resting_hr REAL,
    body_battery_high REAL,
    body_battery_low REAL,
    stress_avg REAL,
    updated_at TEXT NOT NULL
);
"""

RECOVERY_COLUMNS = [
    "sleep_seconds",
    "sleep_score",
    "hrv_overnight_avg",
    "hrv_status",
    "resting_hr",
    "body_battery_high",
    "body_battery_low",
    "stress_avg",
]


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = Path(db_path or GARMIN_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


# --------------------------------------------------
# Writes (garmin_sync.py only)
# --------------------------------------------------

def start_run(conn, started_at, range_start, range_end) -> int:
    with conn:
        cur = conn.execute(
            "INSERT INTO sync_runs (started_at, range_start, range_end, status) VALUES (?, ?, ?, 'running')",
            (started_at, range_start, range_end),
        )
    return cur.lastrowid


def finish_run(conn, run_id, finished_at, status, endpoints_ok, endpoints_failed, error=None) -> None:
    with conn:
        conn.execute(
            """
            UPDATE sync_runs
            SET finished_at = ?, status = ?, endpoints_ok = ?, endpoints_failed = ?, error = ?
            WHERE id = ?
            """,
            (finished_at, status, endpoints_ok, endpoints_failed, error, run_id),
        )


def save_raw(conn, endpoint, range_start, range_end, fetched_at, payload) -> None:
    with conn:
        conn.execute(
            """
            INSERT INTO raw_responses (endpoint, range_start, range_end, fetched_at, payload)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (endpoint, range_start, range_end)
            DO UPDATE SET fetched_at = excluded.fetched_at, payload = excluded.payload
            """,
            (endpoint, range_start, range_end, fetched_at, json.dumps(payload)),
        )


# --------------------------------------------------
# Field mapping: raw Garmin JSON -> daily_recovery
# --------------------------------------------------
#
# Garmin's public docs don't list the fields inside these responses, so
# nothing is guessed here. After your first sync, run
#   python garmin_sync.py --describe
# which prints the JSON *structure* (key names and types, no values).
# The confirmed paths then go in FIELD_MAP, e.g.
#   "sleep_summaries": {"date": "calendarDate", "sleep_seconds": "sleepTimeSeconds"}
# Each entry maps an endpoint to {our column: dotted path in one daily item}.
# A list response is treated as one item per day; "date" says where the date is.

# Confirmed from `garmin_sync.py --describe` on 2026-11-04 (field names only).
FIELD_MAP: dict[str, dict[str, str]] = {
    "sleep_summaries": {
        "date": "calendarDate",
        "sleep_seconds": "sleepTimeSeconds",
        "sleep_score": "sleepScores.overall.value",
    },
    "hrv_summaries": {  # response: {"hrvSummaries": [...], "userProfilePk": ...}
        "date": "calendarDate",
        "hrv_overnight_avg": "lastNightAvg",
        "hrv_status": "status",
    },
    "daily_summaries": {  # response: {"data": [...]}
        "date": "calendarDate",
        "resting_hr": "heartRate.restingValue",
        "body_battery_high": "bodyBattery.maxValue",
        "body_battery_low": "bodyBattery.minValue",
        "stress_avg": "stress.avgLevel",
    },
}

# Garmin uses 0 or negative numbers for "no reading" on these.
POSITIVE_ONLY = {"sleep_seconds", "sleep_score", "hrv_overnight_avg", "resting_hr", "stress_avg"}


def _dig(item, dotted_path):
    value = item
    for part in dotted_path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _daily_items(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        # Common wrappers: a single list value holds the daily items.
        lists = [v for v in payload.values() if isinstance(v, list)]
        if len(lists) == 1:
            return lists[0]
        return [payload]
    return []


def extract_daily_recovery(conn, updated_at, field_map=None) -> int:
    """Rebuild daily_recovery from raw_responses using FIELD_MAP. Returns rows written."""

    field_map = FIELD_MAP if field_map is None else field_map
    by_date: dict[str, dict] = {}

    for row in conn.execute("SELECT endpoint, payload FROM raw_responses"):
        mapping = field_map.get(row["endpoint"])
        if not mapping or "date" not in mapping:
            continue
        for item in _daily_items(json.loads(row["payload"])):
            if not isinstance(item, dict):
                continue
            day = _dig(item, mapping["date"])
            if not isinstance(day, str) or len(day) < 10:
                continue
            day = day[:10]
            for column, path in mapping.items():
                if column in RECOVERY_COLUMNS:
                    value = _dig(item, path)
                    if value is None or isinstance(value, (dict, list)):
                        continue
                    if column in POSITIVE_ONLY and (not isinstance(value, (int, float)) or value <= 0):
                        continue
                    by_date.setdefault(day, {})[column] = value

    with conn:
        for day, values in by_date.items():
            cols = ["date", *values.keys(), "updated_at"]
            placeholders = ", ".join("?" for _ in cols)
            updates = ", ".join(f"{c} = excluded.{c}" for c in [*values.keys(), "updated_at"])
            conn.execute(
                f"INSERT INTO daily_recovery ({', '.join(cols)}) VALUES ({placeholders}) "
                f"ON CONFLICT (date) DO UPDATE SET {updates}",
                (day, *values.values(), updated_at),
            )

    return len(by_date)


# --------------------------------------------------
# Reads (coach + dashboard)
# --------------------------------------------------

def get_daily_recovery(since_date: str, db_path: Path | None = None) -> list[dict]:
    """Daily recovery rows on/after `since_date`, oldest first. [] if no Garmin data."""

    path = Path(db_path or GARMIN_DB_PATH)
    if not path.exists():
        return []

    conn = connect(path)
    rows = [
        dict(r)
        for r in conn.execute("SELECT * FROM daily_recovery WHERE date >= ? ORDER BY date", (since_date,))
    ]
    conn.close()
    return rows


def get_last_sync(db_path: Path | None = None) -> dict | None:
    path = Path(db_path or GARMIN_DB_PATH)
    if not path.exists():
        return None

    conn = connect(path)
    row = conn.execute("SELECT * FROM sync_runs ORDER BY id DESC LIMIT 1").fetchone()
    raw_count = conn.execute("SELECT COUNT(*) FROM raw_responses").fetchone()[0]
    mapped_days = conn.execute("SELECT COUNT(*) FROM daily_recovery").fetchone()[0]
    conn.close()

    if row is None:
        return None

    return {**dict(row), "raw_responses": raw_count, "mapped_days": mapped_days, "fields_mapped": bool(FIELD_MAP)}


def describe_raw(conn) -> dict[str, list[str]]:
    """Key names and value types per endpoint — never values."""

    def shape(value, prefix, out, depth=0):
        if depth > 6:
            return
        if isinstance(value, dict):
            for key, sub in value.items():
                path = f"{prefix}.{key}" if prefix else key
                out.add(f"{path}: {type(sub).__name__}")
                shape(sub, path, out, depth + 1)
        elif isinstance(value, list) and value:
            shape(value[0], f"{prefix}[]", out, depth + 1)

    result: dict[str, set] = {}
    for row in conn.execute("SELECT endpoint, payload FROM raw_responses"):
        shape(json.loads(row["payload"]), "", result.setdefault(row["endpoint"], set()))

    return {endpoint: sorted(keys) for endpoint, keys in result.items()}


def get_recent_activities(since_date: str, db_path: Path | None = None) -> list[dict]:
    """
    Activities your watch recorded, newest first, as a small summary:
    date, type, minutes, miles, avg/max HR, Garmin training load.
    Only activity fields are read (never names or profile fields).
    """

    path = Path(db_path or GARMIN_DB_PATH)
    if not path.exists():
        return []

    conn = connect(path)
    seen: dict = {}
    for row in conn.execute("SELECT payload FROM raw_responses WHERE endpoint = 'activities'"):
        for a in _daily_items(json.loads(row["payload"])):
            if not isinstance(a, dict):
                continue
            day = str(a.get("startTimeLocal") or "")[:10]
            if len(day) < 10 or day < since_date:
                continue
            key = a.get("activityId") or (day, a.get("beginTimestamp"))

            def num(name, scale=1.0, digits=1):
                v = a.get(name)
                return round(v * scale, digits) if isinstance(v, (int, float)) and v > 0 else None

            seen[key] = {
                "activity_id": a.get("activityId") if isinstance(a.get("activityId"), int) else None,
                "date": day,
                "type": (_dig(a, "activityType.typeKey") or "other"),
                "minutes": num("duration", 1 / 60, 0),
                "miles": num("distance", 1 / 1609.344, 2),
                "avg_hr": num("averageHR", 1, 0),
                "max_hr": num("maxHR", 1, 0),
                "training_load": num("activityTrainingLoad", 1, 0),
                "aerobic_effect": num("aerobicTrainingEffect", 1, 1),
            }
    conn.close()
    return sorted(seen.values(), key=lambda x: x["date"], reverse=True)
