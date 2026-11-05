#!/usr/bin/env bash
# KaisenOS one-time setup (macOS / Linux). Safe to re-run.
#
# Installs into this folder only (no system-wide changes, no admin
# rights). Your personal data is NOT stored here; see PRIVACY.md.

set -euo pipefail
cd "$(dirname "$0")"
APP="Fitness"

say() { printf "\n\033[1m%s\033[0m\n" "$1"; }
fail() { printf "\n\033[31m%s\033[0m\n" "$1"; exit 1; }

[[ "$(id -u)" == "0" ]] && fail "Please run setup as your normal user, not root/sudo."

say "1/5  Checking Python (3.12+ needed)"
PY="$(command -v python3 || true)"
[[ -z "$PY" ]] && fail "python3 not found. Install Python 3.12+ from https://www.python.org/downloads/"
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' \
  || fail "Python 3.12+ is needed (found $("$PY" --version)). Install it from https://www.python.org/downloads/"
echo "OK: $("$PY" --version)"

say "2/5  Installing Python packages into $APP/.venv"
[[ -d "$APP/.venv" ]] || "$PY" -m venv "$APP/.venv"
"$APP/.venv/bin/python3" -m pip install --quiet --upgrade pip
"$APP/.venv/bin/python3" -m pip install --quiet --require-virtualenv -r "$APP/requirements.txt"
echo "OK"

say "3/5  Building the dashboard"
if command -v npm >/dev/null 2>&1; then
  (cd "$APP/frontend" && npm ci --no-audit --no-fund --loglevel=error && npm run build --silent >/dev/null)
  echo "OK"
elif [[ -f "$APP/frontend/dist/index.html" ]]; then
  echo "Node.js not found, but a pre-built dashboard is present. OK"
else
  fail "Node.js 20+ is needed to build the dashboard: https://nodejs.org (or download a release zip that includes it)."
fi

say "4/5  Checking Ollama (the local AI model runner)"
if ! command -v ollama >/dev/null 2>&1; then
  echo "Ollama isn't installed. The app works without it, but the AI coach needs it."
  echo "Install it from https://ollama.com, then re-run ./setup.sh to pick a model."
else
  # Pick a model that fits this computer's memory.
  if [[ "$(uname)" == "Darwin" ]]; then RAM_GB=$(( $(sysctl -n hw.memsize) / 1073741824 ));
  else RAM_GB=$(( $(awk '/MemTotal/ {print $2}' /proc/meminfo) / 1048576 )); fi
  if   (( RAM_GB >= 16 )); then MODEL="gpt-oss:20b"; SIZE="~13 GB"
  elif (( RAM_GB >= 8 ));  then MODEL="qwen3:8b";    SIZE="~5 GB"
  else                          MODEL="llama3.2:3b"; SIZE="~2 GB"; fi
  echo "This computer has ${RAM_GB} GB of memory. Recommended model: $MODEL ($SIZE download)."
  if ollama list 2>/dev/null | awk 'NR>1 {print $1}' | grep -qx "$MODEL"; then
    echo "Already downloaded. OK"
  else
    read -r -p "Download $MODEL now? [y/N] " answer
    [[ "$answer" =~ ^[Yy]$ ]] && ollama pull "$MODEL" || echo "Skipped. Later: ollama pull $MODEL"
  fi
  # Tell the app which model to use (stored with your data, not in this folder).
  (cd "$APP" && .venv/bin/python3 -c "
from backend.config import load_settings, save_settings
from src.paths import make_private
make_private(); s = load_settings(); s['ollama_model'] = '$MODEL'; save_settings(s)")
  echo "Coach model set to $MODEL (change any time in Settings)."
fi

say "5/5  Garmin (optional)"
if [[ -f .env ]]; then
  chmod 600 .env
  echo ".env found (permissions set to owner-only)."
else
  echo "Skipped. To use Garmin later: cp .env.example .env, add your key, chmod 600 .env"
fi

say "Done. Start KaisenOS with:  ./start.sh        (or ./start.sh --demo to try it with made-up data)"
