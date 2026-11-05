"""
Garmin sync — the ONLY code in this project that uses the internet.

Run by hand from the Fitness/ folder (or daily at 8:00 am via
scripts/garmin_schedule.sh install, which runs this same script):

    .venv/bin/python3 garmin_sync.py              # last 14 days
    .venv/bin/python3 garmin_sync.py --days 30
    .venv/bin/python3 garmin_sync.py --describe   # show field NAMES in saved data (no values)
    .venv/bin/python3 garmin_sync.py --remap      # offline: re-read saved data into recovery days

What it does
- Reads GARMIN_PERSONAL_API_KEY from the .env file (via python-dotenv).
- Exchanges the key for a fresh 24-hour access token (every run; Garmin
  doesn't support refresh tokens). The key and token are never printed,
  logged, or saved.
- Pulls data from Garmin's Personal API and saves it to
  data/garmin_data.sqlite. Pull-only: it never reads or sends anything
  from your workout log, and talks to no host except Garmin's API.

Endpoints and auth follow Garmin's docs
(developer.garmin.com/gc-developer-program/personal/personal-api) and
Garmin's official client (github.com/garmin/connect-personal-api-python).
"""

import argparse
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from src import garmin_store  # noqa: E402

API_HOST = "personal.connectapi.garmin.com"
BASE_URL = f"https://{API_HOST}"
TOKEN_PATH = "/personalapitoken-service/personal-api/personal-api-key/token"
KEY_ENV_VAR = "GARMIN_PERSONAL_API_KEY"
NEW_KEY_URL = "https://connect.garmin.com/app/settings/personalApiToken"

# Garmin doesn't document a maximum date range, so request a week at a time.
CHUNK_DAYS = 7

# name -> function(start, end) returning (path, params)
ENDPOINTS = {
    "sleep_summaries": lambda s, e: (
        "/sleep-service/sleep/dailySleepSummariesByDate",
        {"startDate": s, "endDate": e},
    ),
    "hrv_summaries": lambda s, e: (f"/hrv-service/hrv/daily/{s}/{e}", None),
    "daily_summaries": lambda s, e: (
        "/usersummary-service/v2/dailysummaries",
        {"startDate": s, "endDate": e},
    ),
    "body_battery": lambda s, e: (
        "/wellness-service/wellness/bodyBattery/reports/daily",
        {"startDate": s, "endDate": e},
    ),
    "stress": lambda s, e: (f"/usersummary-service/stats/stress/daily/{s}/{e}", None),
    "activities": lambda s, e: (
        "/activitylist-service/activities/search/activities",
        {"start": 0, "limit": 100, "startDate": s, "endDate": e},
    ),
}


class SyncError(Exception):
    """A problem worth stopping for, with a message safe to print."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_api_key() -> str:
    # .env lives in the project root (Kaisen/); also accept Fitness/.env.
    here = Path(__file__).resolve().parent
    for env_file in (here.parent / ".env", here / ".env"):
        if env_file.exists():
            load_dotenv(env_file, override=False)

    import os

    key = (os.environ.get(KEY_ENV_VAR) or "").strip()
    if not key:
        raise SyncError(
            f"{KEY_ENV_VAR} isn't set. Add it to the .env file in the project root "
            f"(create a key at {NEW_KEY_URL})."
        )
    return key


def make_client(transport: httpx.BaseTransport | None = None) -> httpx.Client:
    client = httpx.Client(
        base_url=BASE_URL,
        timeout=30,
        follow_redirects=False,  # never follow a redirect to another host
        transport=transport,
        headers={"Accept": "application/json"},
    )
    if urlparse(str(client.base_url)).hostname != API_HOST:
        raise SyncError("Refusing to contact any host other than Garmin's API.")
    return client


def get_access_token(client: httpx.Client, api_key: str) -> str:
    try:
        response = client.post(TOKEN_PATH, headers={"Authorization": f"ApiKey {api_key}", "Accept": "*/*"})
    except httpx.HTTPError as exc:
        raise SyncError(f"Couldn't reach Garmin ({type(exc).__name__}). Check your internet connection.") from None

    if response.status_code in (400, 401, 403):
        raise SyncError(
            f"Garmin rejected your API key (HTTP {response.status_code}). It has probably expired "
            "(keys last 30 days to 1 year) or been deleted.\n"
            f"Create a new key at {NEW_KEY_URL}, then replace {KEY_ENV_VAR} in your .env file."
        )
    if response.status_code == 429:
        raise SyncError("Garmin is rate-limiting requests (HTTP 429). Wait a while and try again.")
    if not response.is_success:
        raise SyncError(f"Garmin's token service returned HTTP {response.status_code}. Try again later.")

    # Garmin returns the token as plain text (a JWT), not JSON.
    token = response.text.strip()
    if token.count(".") != 2:
        raise SyncError("Garmin's token service returned an unexpected response (not a token).")
    return token


def date_chunks(start: date, end: date, size: int = CHUNK_DAYS):
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=size - 1), end)
        yield cursor.isoformat(), chunk_end.isoformat()
        cursor = chunk_end + timedelta(days=1)


def run_sync(
    days: int,
    *,
    api_key: str,
    db_path: Path | None = None,
    transport: httpx.BaseTransport | None = None,
    today: date | None = None,
    log=print,
) -> dict:
    """Pull `days` days of data ending today. Returns a summary of counts."""

    end = today or date.today()
    start = end - timedelta(days=days - 1)
    conn = garmin_store.connect(db_path)
    run_id = garmin_store.start_run(conn, _now(), start.isoformat(), end.isoformat())
    ok = failed = 0
    errors: list[str] = []

    try:
        with make_client(transport) as client:
            token = get_access_token(client, api_key)
            auth = {"Authorization": f"Bearer {token}"}
            log(f"Got a fresh access token. Pulling {start} to {end}...")

            for name, build in ENDPOINTS.items():
                saved = 0
                for chunk_start, chunk_end in date_chunks(start, end):
                    path, params = build(chunk_start, chunk_end)
                    try:
                        response = client.get(path, params=params, headers=auth)
                    except httpx.HTTPError as exc:
                        raise SyncError(f"Lost connection to Garmin ({type(exc).__name__}).") from None

                    if response.status_code in (401, 403):
                        raise SyncError(
                            f"Garmin stopped accepting the access token (HTTP {response.status_code}). "
                            f"If this keeps happening, your API key may have been revoked. Create a new one at {NEW_KEY_URL}."
                        )
                    if response.status_code == 429:
                        raise SyncError("Garmin is rate-limiting requests (HTTP 429). Wait a while and try again.")
                    if response.status_code == 204 or not response.content:
                        payload = None
                    elif response.is_success:
                        try:
                            payload = response.json()
                        except ValueError:
                            failed += 1
                            errors.append(f"{name} {chunk_start}: response wasn't JSON")
                            continue
                    else:
                        failed += 1
                        errors.append(f"{name} {chunk_start}..{chunk_end}: HTTP {response.status_code}")
                        continue

                    garmin_store.save_raw(conn, name, chunk_start, chunk_end, _now(), payload)
                    saved += 1
                    ok += 1

                log(f"  {name}: {saved} range(s) saved")

        mapped = garmin_store.extract_daily_recovery(conn, _now())
        status = "ok" if failed == 0 else "partial"
        garmin_store.finish_run(conn, run_id, _now(), status, ok, failed, "; ".join(errors) or None)
        return {"status": status, "saved": ok, "failed": failed, "errors": errors, "mapped_days": mapped}

    except SyncError as exc:
        garmin_store.finish_run(conn, run_id, _now(), "failed", ok, failed, str(exc))
        raise
    finally:
        conn.close()


def main(argv=None) -> int:
    from src.paths import make_private

    make_private()
    parser = argparse.ArgumentParser(description="Pull your Garmin data into data/garmin_data.sqlite.")
    parser.add_argument("--days", type=int, default=14, help="how many days back to pull (default 14, max 365)")
    parser.add_argument("--describe", action="store_true", help="print field names in saved data (no values) and exit")
    parser.add_argument("--remap", action="store_true", help="offline: rebuild recovery days from already-saved data and exit")
    args = parser.parse_args(argv)

    if args.describe:
        conn = garmin_store.connect()
        shapes = garmin_store.describe_raw(conn)
        conn.close()
        if not shapes:
            print("No Garmin data saved yet. Run a sync first.")
            return 1
        for endpoint, keys in shapes.items():
            print(f"\n[{endpoint}]  ({len(keys)} fields)")
            for key in keys:
                print(f"  {key}")
        return 0

    if args.remap:
        conn = garmin_store.connect()
        days = garmin_store.extract_daily_recovery(conn, _now())
        filled = {
            col: conn.execute(f"SELECT COUNT({col}) FROM daily_recovery").fetchone()[0]
            for col in garmin_store.RECOVERY_COLUMNS
        }
        conn.close()
        print(f"Recovery data mapped for {days} day(s). Days with each field:")
        for col, count in filled.items():
            print(f"  {col}: {count}")
        return 0

    if not 1 <= args.days <= 365:
        parser.error("--days must be between 1 and 365")

    print(f"=== Garmin sync {datetime.now().strftime('%Y-%m-%d %H:%M')} (last {args.days} days) ===", flush=True)
    try:
        summary = run_sync(args.days, api_key=load_api_key())
    except SyncError as exc:
        print(f"\nGarmin sync failed: {exc}", file=sys.stderr)
        return 1

    print(f"\nDone ({summary['status']}): {summary['saved']} range(s) saved, {summary['failed']} failed.")
    for error in summary["errors"]:
        print(f"  - {error}")
    if not garmin_store.FIELD_MAP:
        print(
            "\nNext step: run `.venv/bin/python3 garmin_sync.py --describe` and share the output "
            "(field names only, no values) so the coach can be wired to your sleep/HRV fields."
        )
    else:
        print(f"Recovery data mapped for {summary['mapped_days']} day(s).")
    return 0 if summary["status"] == "ok" else 2


if __name__ == "__main__":
    sys.exit(main())
