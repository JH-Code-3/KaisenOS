#!/bin/zsh
# Daily Garmin sync at 8:00 am, run by macOS (launchd) as you.
#
#   scripts/garmin_schedule.sh install    turn the daily 8:00 am sync on
#   scripts/garmin_schedule.sh uninstall  turn it off
#   scripts/garmin_schedule.sh status     is it on? when did it last run?
#   scripts/garmin_schedule.sh run-now    run the scheduled job once, right now
#
# It runs the same pull-only garmin_sync.py you can run by hand. If your
# Mac is asleep at 8:00, it runs as soon as the Mac wakes; if it's shut
# down, that day is skipped. Output (counts and errors only) goes to
# data/garmin_sync.log.

set -euo pipefail

LABEL="com.kaisen.garmin-sync"
FITNESS_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$FITNESS_DIR/.venv/bin/python3"
SCRIPT="$FITNESS_DIR/garmin_sync.py"
DATA_DIR="$(cd "$FITNESS_DIR" && "$PYTHON" -c 'from src.paths import DATA_DIR; print(DATA_DIR)')"
LOG="$DATA_DIR/garmin_sync.log"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
DOMAIN="gui/$(id -u)"
HOUR=8
MINUTE=0

install() {
  mkdir -p "$HOME/Library/LaunchAgents" "$DATA_DIR"
  cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON</string>
    <string>$SCRIPT</string>
    <string>--days</string>
    <string>7</string>
  </array>
  <key>WorkingDirectory</key><string>$FITNESS_DIR</string>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key><integer>$HOUR</integer>
    <key>Minute</key><integer>$MINUTE</integer>
  </dict>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
  <key>ProcessType</key><string>Background</string>
</dict>
</plist>
PLIST
  launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
  launchctl bootstrap "$DOMAIN" "$PLIST"
  echo "Daily Garmin sync is ON: every day at $(printf '%d:%02d' $HOUR $MINUTE) am."
}

uninstall() {
  launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
  rm -f "$PLIST"
  echo "Daily Garmin sync is OFF. (Run garmin_sync.py by hand any time.)"
}

status() {
  if launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1; then
    echo "Daily Garmin sync: ON (every day at $(printf '%d:%02d' $HOUR $MINUTE) am)"
    launchctl print "$DOMAIN/$LABEL" | grep -E "last exit code|runs =" | sed 's/^[[:space:]]*/  /'
  else
    echo "Daily Garmin sync: OFF"
  fi
  [[ -f "$LOG" ]] && { echo "Last log lines:"; tail -n 4 "$LOG" | sed 's/^/  /'; } || true
}

run_now() {
  launchctl kickstart -p "$DOMAIN/$LABEL" >/dev/null
  echo "Started. Check with: scripts/garmin_schedule.sh status"
}

case "${1:-}" in
  install) install ;;
  uninstall) uninstall ;;
  status) status ;;
  run-now) run_now ;;
  *) echo "usage: $0 install | uninstall | status | run-now"; exit 1 ;;
esac
