#!/usr/bin/env bash
# Start KaisenOS on this computer only (http://127.0.0.1:8000).
#   ./start.sh          your data
#   ./start.sh --demo   made-up demo data in a temporary folder
set -euo pipefail
cd "$(dirname "$0")/Fitness"
[[ -x .venv/bin/python3 ]] || { echo "Run ./setup.sh first."; exit 1; }
exec .venv/bin/python3 run.py "$@"
