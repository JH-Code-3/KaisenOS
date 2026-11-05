# Privacy

KaisenOS is software you download and run on your own computer. **The people who make KaisenOS never receive your data.** There is no account, no server, no analytics and no telemetry. This page describes exactly what the app stores and every network connection it can make.

## What it stores

Only what you enter or choose to import:

| Kind | Examples |
|---|---|
| Training | lifting sets, reps, weights, RPE, pain ratings; runs, practices, games, sprints, jumps |
| Nutrition | meals, foods, calories and macros, daily targets, saved foods |
| Recovery & body | sleep, energy, soreness, pain check-ins; body weight, body fat, waist |
| Goals & profile | phase plans; optional sex, birth year, height and experience (used only to estimate calories) |
| Planner | weekly plans and your usual weekly availability |
| Imports | pasted notes are read on your computer and **not saved as a whole**; only the entries you approve are saved, sometimes with a short snippet as a note (e.g. "felt great") |
| Garmin (optional) | sleep, HRV, resting heart rate, body battery, stress and activities from your own Garmin account |
| Settings | which local AI model to use |

It does **not** ask for your name, email, location, contacts or any account.

## Where it's stored

Everything is in **one folder on your computer**, outside the app's code:

- macOS: `~/Library/Application Support/KaisenOS`
- Linux: `~/.local/share/KaisenOS` (or `$XDG_DATA_HOME/KaisenOS`)
- Windows: `%APPDATA%\KaisenOS`
- or any folder you set with `KAISEN_DATA_DIR`

The exact path is shown in **Settings → Your data**. On macOS and Linux, the folder is readable only by your user account (permissions `0700` for folders and `0600` for files).

**Encryption:** KaisenOS does **not** encrypt its data files itself. Protect them with your operating system's full-disk encryption: FileVault on macOS, BitLocker on Windows, LUKS on Linux.

## Network connections: every one

| Connection | When | What is sent | What comes back |
|---|---|---|---|
| Your browser ↔ KaisenOS at `127.0.0.1:8000` | While the app runs | Your actions in the dashboard | Your dashboard |
| KaisenOS ↔ Ollama at `localhost:11434` | When you use the AI coach or import notes | Your question plus the relevant logs, **to the local model only** | The model's reply |
| **Garmin sync** ↔ `personal.connectapi.garmin.com` (HTTPS) | Only if you set up Garmin, and only when you run the sync or turn on the daily sync | Your Garmin API key (to get a 24-hour access token), then requests for date ranges | Your own Garmin data |
| Package downloads | Only during `./setup.sh` | Standard requests to PyPI, npm and Ollama for the app's dependencies and the model you choose | Software |

That's all of them:

- **The app itself makes no internet requests.** The dashboard's content security policy blocks loading anything from other websites, and an automated test fails if network code appears anywhere other than the Garmin sync.
- **The Garmin sync only downloads.** It never sends anything from your logs to Garmin.
- **The AI model runs locally.** The app refuses to use Ollama "cloud" models, refuses any Ollama address other than this computer, and ignores proxy settings and redirects.
- **Ollama itself is separate software.** KaisenOS doesn't control Ollama's own behavior, such as update checks. See [Ollama's documentation](https://github.com/ollama/ollama).

## Backups

- A backup is made **automatically once a day** when the app starts, and **before any restore**. You can also back up anytime from Settings.
- The **newest 10** backups are kept; older ones are deleted automatically.
- Backups sit in the same private folder (`backups/`) and, like everything else, are **not encrypted by the app**.

## Your control

- **Export**: Settings → *Export everything (JSON)* or *Export as spreadsheets (CSV zip)*. Downloads go to your browser's download folder, which is outside the app's control.
- **Restore**: Settings → Backups → *Restore*. Your current data is backed up first.
- **Delete**: Settings → *Delete all my data* (type `DELETE`). This removes the training log, Garmin data, settings, exports and sync log, and optionally all backups.

**What deletion can't reach:**
- copies you made (downloaded exports, Time Machine or other backups of your computer)
- data in your Garmin account
- your Garmin key in `.env` (delete that file yourself)
- AI models you downloaded with Ollama

Deleted files may remain recoverable on disk until they're overwritten. Full-disk encryption reduces this risk.

## AI coach

- The coach's replies come from a language model running on your computer. They can be wrong.
- Anything the model reads from your notes is shown for review, and nothing is saved until you confirm it.
- Numbers like calorie targets, training loads and progression are calculated by the app's code, not by the model.

## Not medical advice

KaisenOS provides general fitness information. It does not diagnose, treat or prevent any condition. For pain, injury or health concerns, see a doctor or physical therapist.

For regulatory background, see [docs/REGULATORY_NOTES.md](docs/REGULATORY_NOTES.md). Security details are in [SECURITY.md](SECURITY.md).
