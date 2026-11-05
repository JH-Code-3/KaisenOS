# Local AI Fitness & Performance Dashboard

A privacy-first, locally hosted fitness and athletic-performance dashboard powered by **Python, SQLite, and Ollama**. The application is designed to track nutrition, training, running, recovery, and body composition, while a local AI coach helps organize entries, analyze real history, and suggest improvements.

> **Project status:** This README describes the intended product and implementation requirements. It is not a claim that every feature is already implemented. Inspect the repository and verify existing functionality before making changes.

## Vision

Build a polished, responsive fitness application that works on my own computer without cloud hosting, cloud AI, or external storage of personal information. Make natural-language logging convenient, but keep manual controls, transparent calculations, and accurate data as the source of truth.

### Primary capabilities

- Log meals, individual foods, serving sizes, calories, protein, carbohydrates, fat, and optionally fiber.
- Record strength workouts with **individual sets**, repetitions, weights, RPE, rest, pain, and notes.
- Track running, sprinting, plyometrics, agility, and conditioning.
- Track sleep, recovery, soreness, energy, stress, and body measurements.
- Visualize body-weight trends, estimated 1RM, training volume, macro averages, and progress toward goals.
- Chat with a **locally running Ollama model** that can interpret entries, retrieve records, explain trends, and propose changes.
- Generate data-driven weekly workout plans and export them to Excel.
- Optionally import Garmin data through a genuinely offline method.
- Optionally look up **public food nutrition facts** online without sending personal records or full chat messages.

## Existing project: preserve and extend

The repository may already contain:

```text
Fitness/
├── .venv/
├── coach.py
├── README.md
├── requirements.txt
├── knowledge/
│   └── 90_Day_Athletic_Body_Transformation_AI_Coach_Blueprint.pdf
├── data/
│   └── athlete.db
├── workouts/
│   └── weekly Excel workbooks
└── src/
    ├── database.py
    ├── analytics.py
    ├── log_workout.py
    ├── weekly_planner.py
    └── excel_generator.py
```

Existing technologies include Python, SQLite, Ollama (`gpt-oss:20b`), `openpyxl`, and `pypdf`. Existing code may support controlled logging, database retrieval, deterministic analytics, progression recommendations, and weekly workbook generation.

**Before implementation:** inspect the actual files and database schema. Reuse working functions, preserve existing athlete records, and avoid rebuilding or overwriting functioning components. Make a backup before schema migrations.

## Proposed architecture

```text
Local browser / React dashboard
            │
            ▼
    FastAPI backend (localhost)
            │
      ┌─────┼───────────────┐
      ▼     ▼               ▼
  SQLite  Python tools   Ollama (local)
      │     │               │
      └─────┴───────────────┘
            │
     Optional controlled
     public-food lookup
     (disabled by default)
```

### Preferred stack

| Layer | Technology | Purpose |
| --- | --- | --- |
| Frontend | React, TypeScript, Vite | Responsive application |
| Styling | Tailwind CSS, Lucide icons | Clean, modern interface |
| Charts | Recharts | Interactive progress visualizations |
| Backend | Python, FastAPI, Pydantic | API, validation, controlled actions |
| Storage | SQLite | Local persistent source of truth |
| Database access | Existing data layer or SQLAlchemy | Safe, maintainable queries |
| AI | Ollama with `gpt-oss:20b` by default | Local interpretation and coaching |
| Workbook export | Existing `openpyxl` generator | Weekly plans and exports |

Recommend architectural changes only when they meaningfully improve maintainability, and explain them before implementation. The app should run locally without an internet connection after setup.

## Dashboard experience

Design a professional athletic-performance application rather than a generic admin panel:

- Dark mode by default, responsive desktop/mobile layouts, clear typography, intuitive navigation.
- At-a-glance cards for daily calories, protein and other macros, current weight, sleep, recent workout, weekly training volume, and progress toward strength goals.
- Interactive trends, goal progress, informative empty states, and clear distinctions between observed and estimated metrics.
- Dedicated pages for **Overview, Nutrition, Workouts, Running & Athleticism, Recovery, Body Composition, AI Coach, Weekly Planner, and Settings/Privacy**.
- Manual entry must work even when Ollama is stopped.

## Nutrition and food logging

Support both manual entry and natural-language input, for example:

> “For breakfast I had three eggs, two slices of bacon, and a protein shake.”

The system should:

1. Parse foods, quantities, serving units, and meal type.
2. Match entries against a **local food catalog**, saved foods, recipes, and recent meals.
3. Calculate calories, protein, carbohydrates, fat, and fiber when available.
4. Present a **structured preview** with sources and uncertainty labels.
5. Allow corrections before saving.
6. Save the confirmed meal and individual food items in SQLite.
7. Immediately update daily totals and trends.

Support branded foods, custom foods, manual nutrition-label entry, serving conversions, saved recipes, and frequent meals. Where reliable values are unavailable, show **estimated** values rather than invented precision. Allow an optional, explicitly initiated import of a reputable public food dataset (such as USDA FoodData Central) into local storage.

**Nutrition analytics:** daily totals versus targets, seven-day averages, macro trends, calorie intake versus estimated maintenance, and relationships between weight trends and intake. Avoid treating estimated calorie expenditure or maintenance as exact.

## Strength and workout logging

Store **sessions, exercises, and individual sets** rather than only one aggregated weight per exercise. Capture date/time, exercise, set number, reps, weight, RPE, rest, pain, duration, and notes.

Example:

> “I benched 160 pounds for three sets of five. My last set was RPE 9.”

Show the interpreted sets and ask for confirmation before writing. Allow edits, corrections, and deletion of incorrect entries.

Include an exercise library, reusable workout templates, workout history, personal records, estimated 1RM, volume load, frequency, muscle-group volume, and progression suggestions.

Use deterministic Python for calculations:

- **Set volume load:** weight × repetitions; sum across completed sets.
- **Estimated 1RM:** use a documented formula (for example, Epley) and label it as an estimate.
- **Progression:** consider completed performance, RPE, pain, recovery, and exercise-specific constraints.
- **Trend analysis:** distinguish meaningful comparisons from insufficient data.

**Never treat a planned workout as a completed workout.** Never invent missing workout history or assume prescribed loads were achieved.

## Running and athletic performance

Track running distance, duration, pace, RPE, sprint distances/times, jump performance, plyometric drills, agility work, conditioning, and session notes. Visualize pace and workload trends without combining incompatible metrics or making unsupported comparisons.

## Sleep, recovery, and body composition

Track sleep duration/quality, energy, soreness, pain, stress, recovery notes, weight, estimated body-fat percentage, waist measurement, and optional locally stored progress photos.

Show seven-day sleep averages, weight moving averages, consistency, and trends relative to training and nutrition. Label body-fat measurements and inferred relationships appropriately; correlation is not proof of causation.

## Local Ollama AI coach

Provide an integrated chat interface for questions such as:

- “Log my lunch: half a pound of ground beef, broccoli, and a sweet potato.”
- “How much protein have I eaten today?”
- “Log bench press at 160 pounds for three sets of five, RPE 9.”
- “How has my squat progressed this month?”
- “What should I change next week based on my sleep and training?”
- “Generate my next workout based on what I actually completed.”

### Controlled AI workflow

**Writes:**

```text
User input → local Ollama parsing → validated structured data
           → editable preview → user confirmation
           → controlled Python write → SQLite → dashboard refresh
```

**Reads and coaching:**

```text
User question → authorized database retrieval → Python calculations
              → local Ollama explanation → grounded recommendation
```

Requirements:

- Ollama **never writes directly to SQLite** and never executes unrestricted model-generated SQL or code.
- Use schema-validated structured output (for example, Pydantic) and explicit backend functions.
- Confirm writes and edits before committing; handle duplicate entries and corrections.
- Never claim a record was saved until the backend confirms success.
- Do not hallucinate history, trends, nutritional facts, or calculations.
- Use the existing coaching blueprint, goals, preferences, equipment, time limits, and pain/recovery records when relevant.
- Clearly distinguish observed data, estimates, and general coaching guidance.
- Keep manual logging, dashboards, and analytics functional when the model is unavailable.

## Weekly workout planning

Reuse the existing `weekly_planner.py` and `excel_generator.py` where possible. Provide a seven-day view, editable prescribed workouts, completion logging, and Excel export.

Before preparing the next week, review **actual completed sessions** and recovery data. Never progress a lift merely because it appeared in a previous planned workbook. Keep planned load, actual load, and recommendation separate.

## Garmin integration: offline-first

I use a Garmin smartwatch and would like to import its data **without sending personal information to Garmin Connect, other cloud services, or third-party servers through this application**.

**Investigate before implementation** whether these methods genuinely meet that requirement:

- Garmin Health API and Garmin Connect Developer Program.
- Garmin Connect IQ SDK.
- Direct USB/device-to-computer transfers.
- Local FIT, GPX, TCX, and CSV imports.
- Direct Bluetooth synchronization, if supported and feasible.
- Relevant open-source parsers and libraries.

Document whether each approach requires Garmin cloud services, account authentication, developer approval, internet connectivity, or a third party. **Do not assume official Garmin APIs are fully offline.** If no supported direct integration satisfies strict privacy, prioritize a local file importer and explain the limitations.

Where genuinely available from the chosen source, import steps, heart rate, resting heart rate, HRV, sleep duration/stages/score, Body Battery, stress, calories burned, running and GPS activities, training load/readiness, VO2 max, and recovery metrics. Do not invent proprietary or missing measurements. Preserve timestamps, time zones, units, provenance, and prevent duplicate imports.

**Important distinction:** this app cannot guarantee that Garmin's own device firmware or separately installed Garmin software never synchronizes with Garmin's servers. Explain any such limitations; do not silently enable cloud synchronization.

## Strict local privacy and controlled internet access

**Non-negotiable:** personal workout records, meal history, sleep, recovery, weight, Garmin data, goals, photos, and AI chat history must remain on my computer. Do not transmit or store them with cloud AI, cloud databases, third-party analytics, telemetry, remote logging, or cloud authentication.

- Bind local backend services to `localhost` by default.
- Store all records and files locally; use local Ollama inference only.
- Do not load external fonts, scripts, trackers, or analytics in normal operation.
- Provide database backup/restore and export controls.
- Protect against SQL injection, unsafe file paths, unvalidated requests, and unintended network exposure.
- Provide a prominent **Offline Mode** control that disables all app-initiated external requests.

### Optional public-food lookup

Internet access may be used **only when explicitly enabled** to retrieve public nutritional facts for foods or products that cannot be resolved locally.

For example:

- **Permitted minimal query:** `Chick-fil-A chicken sandwich nutrition facts`
- **Prohibited query:** a full personal chat message containing my body weight, health goals, and eating history.

Enforce these boundaries in backend code, not only in prompts:

1. External lookup is **off by default** and requires informed opt-in.
2. Use a tightly scoped allowlist of approved nutrition sources.
3. Send only the minimum food name or barcode needed for lookup.
4. Never send full conversations, database records, health measurements, or identifying context.
5. Validate outgoing requests and incoming data; avoid telemetry, trackers, and unnecessary identifiers.
6. Cache returned public nutrition data locally with source and retrieval date.
7. Label estimated values and allow corrections.
8. Maintain a **local outbound-request log** showing what was sent.
9. Provide a way to disable the feature immediately.
10. Clearly disclose that even minimal food queries may be visible to the external service and may reveal food interests or habits.

The Ollama model must **not** have unrestricted internet access. If a lookup is needed, it requests a narrow, validated Python nutrition-lookup tool. The application must not leak user data in URLs, headers, error reports, or prompts.

### Network boundaries

| Component | Network policy |
| --- | --- |
| React dashboard and FastAPI | Localhost only |
| SQLite and file storage | Local only |
| Ollama and coaching | Local only |
| Garmin processing | Local import preferred; no cloud dependency |
| Workout/nutrition analytics | Local only |
| Public-food lookup | Optional, allowlisted, minimal requests, off by default |

## Data model and migrations

Inspect the current SQLite schema first. Consider normalized tables for:

- Exercises, workout sessions, workout exercises, individual sets.
- Running and athletic sessions.
- Foods, servings, meals, meal items, recipes, nutrition targets.
- Body measurements, recovery, goals.
- Weekly plans and plan items.
- Garmin import batches, activities, measurements, and source metadata.
- AI recommendations and optional local chat history.

Use migrations, constraints, parameterized queries, and transactions. **Never drop or overwrite existing records without explicit approval.** Back up the database before any structural change.

## Reliability and tests

Test food parsing, nutrition math, workout parsing, set-level volume, estimated 1RM, pace, trends, CRUD operations, duplicate detection, date/time zones, weekly plan generation, AI confirmation, Ollama outages, and offline operation.

Privacy-specific verification must demonstrate:

- Normal dashboard/manual logging works with internet disabled.
- Local Ollama runs without cloud inference.
- Local Garmin file imports work offline.
- Offline Mode prevents application-initiated external requests.
- No frontend resources are silently loaded from third-party domains.
- No personal data appears in telemetry, outbound requests, or remote logs.
- Data persists after restart and can be backed up/restored.

Do not display demo values as actual athlete records; keep demo fixtures clearly labeled and separate.

## Implementation roadmap

1. **Audit existing code and data.** Inventory modules, existing capabilities, schema, tests, and integration points.
2. **Propose architecture.** Identify what to reuse, what to add, and any tradeoffs requiring approval.
3. **Create safe migrations and API.** Preserve historical records and validate all input.
4. **Build dashboard UI.** Overview, charts, navigation, settings, and empty states.
5. **Implement manual logging.** Nutrition, sets/workouts, running, sleep/recovery, and weight.
6. **Integrate local Ollama.** Structured parsing, previews, confirmed writes, and grounded answers.
7. **Implement analytics.** Training load, progression, macro trends, recovery, and goals.
8. **Integrate weekly planning.** Reuse existing logic and Excel exports.
9. **Research and add Garmin import.** Prefer offline local files over cloud APIs.
10. **Add optional controlled food lookup.** Strict allowlist, opt-in, local caching, audit log.
11. **Test privacy and reliability.** Offline operation, no leaks, migrations, edge cases.
12. **Document and polish.** Setup, startup scripts, architecture, troubleshooting, and project explanation.

At every major stage, run tests and demonstrate working behavior before moving on.

## Definition of done

The application is ready when I can open a polished **local** dashboard, log meals and workouts manually or through a local AI chat, review accurate macros and training trends, track recovery and body weight, generate weekly workout plans, and restart without losing records. Garmin data can be imported offline through a supported method; internet nutrition research is optional, minimized, and disabled by default. Personal records are never intentionally transmitted to cloud services.

## Development and learning expectations

I am building this to learn full-stack development, Python, relational databases, local LLM integration, analytics, and safe AI tool orchestration. Explain **what** each major component does, **why** it exists, **how** it connects to the rest of the system, and **how to test it**. Keep explanations practical enough that I can confidently discuss the architecture in technical interviews.

### Instructions for Claude Code

**Start by inspecting the repository and reporting the actual current state.** Then propose an implementation plan and identify anything requiring approval. **Do not immediately rewrite the project, replace working code, migrate the database destructively, enable Garmin cloud synchronization, or add external services.** Preserve local-first privacy as a core design constraint.
