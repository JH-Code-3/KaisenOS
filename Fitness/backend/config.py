"""
Backend-wide settings, persisted to data/settings.json.

Privacy: the main app makes no network calls. The only networked code
in this project is garmin_sync.py, which you run by hand. The AI coach
talks to Ollama on localhost only (see src/local_llm.py).
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
from src.paths import DATA_DIR  # noqa: E402

SETTINGS_PATH = DATA_DIR / "settings.json"

DEFAULT_SETTINGS = {
    "ollama_model": "gpt-oss:20b",
}


def load_settings():
    stored = {}

    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH, "r") as settings_file:
                stored = json.load(settings_file)
        except (json.JSONDecodeError, OSError):
            stored = {}

    # Only known keys; older keys (e.g. the removed food-lookup flags) are dropped.
    return {key: stored.get(key, default) for key, default in DEFAULT_SETTINGS.items()}


def save_settings(settings):
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    clean = {key: settings.get(key, default) for key, default in DEFAULT_SETTINGS.items()}

    with open(SETTINGS_PATH, "w") as settings_file:
        json.dump(clean, settings_file, indent=2)
