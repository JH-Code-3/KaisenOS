# Fitness — Local AI Performance Dashboard

A private training dashboard that runs entirely on this computer: a
FastAPI backend, a React dashboard, a local AI coach (Ollama), and an
optional, manually-run Garmin sync. See `Kaisen/README.md` (one level
up) for the full product spec.

## Running it

**Backend** (from this `Fitness/` directory):

```bash
.venv/bin/uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

**Frontend** (from `Fitness/frontend/`):

```bash
npm run dev
```

Then open http://127.0.0.1:5173. The backend binds to localhost only
and only accepts requests from the Vite dev origin (CORS-restricted).

**AI coach** needs the Ollama app running with a downloaded model
(default `gpt-oss:20b`; change it in Settings). Use it from the
dashboard's AI Coach page, or the CLI:

```bash
.venv/bin/python3 coach.py
```

**Garmin sync** (optional, run by hand whenever you want fresh data):

```bash
.venv/bin/python3 garmin_sync.py            # last 14 days
.venv/bin/python3 garmin_sync.py --days 30
.venv/bin/python3 garmin_sync.py --describe # field NAMES in saved data, no values
.venv/bin/python3 garmin_sync.py --remap    # offline: rebuild recovery days from saved data
```

**Daily sync at 8:00 am** (macOS runs the same script as you; if the Mac
is asleep it runs on wake, if it's off that day is skipped; output goes
to `garmin_sync.log` in your data folder, counts and errors only):

```bash
scripts/garmin_schedule.sh install    # on
scripts/garmin_schedule.sh status     # is it on, last result
scripts/garmin_schedule.sh uninstall  # off
```

Settings and the AI Coach page warn if a sync fails or hasn't run for 2+ days.

Needs `GARMIN_PERSONAL_API_KEY` in the `.env` file in the project root
(`Kaisen/.env`). Create a key at
https://connect.garmin.com/app/settings/personalApiToken. Keys expire
after 30 days to 1 year; the script tells you when yours has.

**Tests** (fake data only, no network):

```bash
.venv/bin/python3 -m pip install -r requirements-dev.txt
.venv/bin/python3 -m pytest
```

## Privacy

- The dashboard and backend make **no internet requests**: no
  analytics, telemetry, or cloud sync.
- `garmin_sync.py` is the **only** code that uses the internet. It is
  pull-only, talks only to Garmin's API, gets a fresh access token each
  run, never prints or stores the key or token, and writes only to
  `garmin_data.sqlite` in your data folder. It never reads the workout log.
- The AI coach talks only to Ollama on localhost (`src/local_llm.py`).
  Non-local URLs, `OLLAMA_HOST`, proxies and redirects are refused, and
  so are Ollama cloud models. Your logs go into the prompt sent to that
  local model and nowhere else.
- `tests/test_privacy.py` fails if network code shows up anywhere else.
- `.env`, `garmin_data.*` and the database files are gitignored, and
  `.claude/settings.json` blocks Claude Code from reading `.env`.

## Layout

```
Fitness/
├── garmin_sync.py        Garmin pull (the only networked code; manual)
├── coach.py              CLI AI coach
├── src/
│   ├── database.py       Legacy flat tables (workouts, body_metrics,
│   │                     recovery, running, nutrition)
│   ├── database_v2.py    Normalized tables (per-set workouts, meals,
│   │                     foods, athletic sessions, goals, plans)
│   ├── migrations.py     Additive-only schema migrations
│   ├── analytics.py      e1RM/volume/trend/progression + recovery thresholds
│   ├── weekly_planner.py Load progression helper (+ legacy CLI template)
│   ├── week_planner.py   Weekly Planner: your session rotation, loads, runs
│   ├── excel_generator.py Weekly workbook export
│   ├── local_llm.py      Localhost-only Ollama client
│   ├── coach_engine.py   Coach analysis (load jumps, readiness, next
│   │                     workout, lifting intensity) + local-LLM explanations
│   ├── phase_engine.py   Cut/bulk/maintain/recomp math: maintenance from
│   │                     your logs, calorie/macro targets, plan progress
│   ├── running_analytics.py Weekly mileage, easy/hard split, PRs, 5K estimate
│   ├── note_import.py    Pasted-notes import (split by day, local LLM
│   │                     extraction, review, save as one undoable batch)
│   └── garmin_store.py   Garmin data file (separate from the workout log)
├── backend/              FastAPI app (routers per dashboard page + coach)
├── frontend/             React + Vite + TS + Tailwind dashboard
├── tests/                Pytest suite on fake data
├── run.py                Launcher (127.0.0.1 only; --demo for made-up data)
└── scripts/              Daily Garmin sync on/off (macOS)
```

Your data is NOT in this folder. It lives in one private per-user folder
(`src/paths.py`): macOS `~/Library/Application Support/KaisenOS`, Linux
`~/.local/share/KaisenOS`, Windows `%APPDATA%\KaisenOS`, or `KAISEN_DATA_DIR`.
Older installs that already had `Fitness/data/athlete.db` keep using it.

```
<data folder>/
├── athlete.db            Your training log (SQLite)
├── garmin_data.sqlite    Garmin data (written only by garmin_sync.py)
├── settings.json         Coach model setting
├── backups/              Daily + manual backups (newest 10 kept)
├── exports/              Generated weekly Excel workbooks
└── garmin_sync.log       Sync results (counts and errors only)
```

## How the coach decides

Numbers come from code, not the model. The coach uses your own logs
first (workouts, runs, recovery check-ins, nutrition, body) and Garmin
only as optional extra detail:

- **Readiness:** a check-in from the last 2 days (sleep < 6 h, energy
  ≤ 4, soreness ≥ 7 → hold; pain ≥ 4 → back off), plus Garmin when
  synced (sleep < 6 h, HRV ≥ 10% under your 7-day baseline, resting HR
  5+ bpm over it → hold).
- **Load jumps:** lifting volume and running miles for the last 7 days
  vs. the 3 weeks before; +10% is flagged, +30% is a big jump.
- **Next workout:** repeats the session type you did longest ago, with
  each lift's load from the progression rules, capped by readiness.
- **Pain** of 4/10 or more in recent logs always shows a "see a doctor
  or physical therapist" notice.

## Importing notes

Paste old notes on the **Import Notes** page. Dates at the start of a
line ("Oct 27", "10/27", "2026-10-27") split the notes into days; the
local model reads each day; you review and edit everything (estimated
calories are marked, lines it didn't understand are listed) and nothing
is saved until you confirm. Each import can be undone as a whole.

## Logging by telling the coach

On the **AI Coach** page, type what you ate or did in plain words
("lunch: burrito bowl ~800 cal. benched 155x5x3 @8, 90 min practice,
felt like a 7, slept 7.5h"). The local model reads it with the same
pipeline as Import Notes, defaults to today (or the day you name), and
shows an editable preview; on Save it goes to Nutrition, Workouts,
Basketball & Running, Recovery and Body, then the coach gives quick
feedback. Recovery and body entries merge with that day's existing
check-in. Undo removes the whole log.

## Phases and goals

The **Goals & Phase** page estimates maintenance calories from your own
intake and weight trend (or a formula from your profile until there's
enough data), lets you plan a cut (0.5–1%/wk), lean bulk
(0.25–0.5%/wk), maintenance or recomp, sets matching nutrition targets,
and checks progress (rate, intake, protein, strength trend, cut length).
The coach discusses the choice with you and helps set the goals.

## Garmin activities -> your log

After a sync, **Basketball & Running** lists watch activities from the
last 30 days that aren't in your log. **Add** copies the date, minutes
and distance (runs/conditioning) from Garmin; you pick the kind
(practice/game/..., easy/tempo/...) and your RPE so it counts toward
load. Each activity can be added once; **Skip** hides it. Strength
workouts aren't listed (log lifts set by set on Workouts).

## Basketball and your schedule

Log practices, games, skills work and pickup on **Basketball & Running**
with minutes and RPE; load = RPE x minutes. The page compares the last
7 days with your usual (4-week average) week and flags spikes above
1.5x. On the **Weekly Planner**, mark each day open, busy, practice or
game (saved as your usual week, or one-off): lifting only goes on open
or practice days, heavy legs stay off the day before a game (or are
made ~10% lighter), and basketball days replace runs.

## Status

Built: Overview, Workouts, Nutrition, Basketball & Running, Recovery,
Body Composition, AI Coach, Goals & Phase, Import Notes, Weekly Planner,
and Settings pages; Garmin sync.


