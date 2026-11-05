#!/usr/bin/env bash
# Make a clean public copy of KaisenOS in a separate folder, with a brand
# new git history (none of this repo's past commits come along).
#
#   tools/export_public.sh ~/Desktop/KaisenOS-public
#
# Copies only files that are part of the project (tracked or new, and not
# gitignored), minus personal material, then scans the result and refuses
# to finish if it finds personal data or secrets. Nothing is pushed.
#
# Commit author: set PUBLIC_GIT_NAME / PUBLIC_GIT_EMAIL (use your GitHub
# "noreply" email to keep your real email private). Defaults below.

set -euo pipefail
SRC="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${1:?usage: tools/export_public.sh <new-folder>}"
NAME="${PUBLIC_GIT_NAME:-KaisenOS}"
EMAIL="${PUBLIC_GIT_EMAIL:-KaisenOS@users.noreply.github.com}"

# Personal or not-for-publication, even if tracked in the private repo.
EXCLUDE_RE='^(Fitness/workouts/|Fitness/knowledge/.*\.pdf$|Fitness/data/|.*\.(db|sqlite|sqlite3|log|xlsx|xls)$|\.env$|.*/\.env$|\.claude/settings\.local\.json$)'

if [[ -e "$DEST" && -n "$(ls -A "$DEST" 2>/dev/null)" ]]; then
  echo "Refusing to write into non-empty folder: $DEST"; exit 1
fi
mkdir -p "$DEST"

cd "$SRC"
count=0
while IFS= read -r -d '' f; do
  [[ -f "$f" ]] || continue
  if [[ "$f" =~ $EXCLUDE_RE ]]; then continue; fi
  mkdir -p "$DEST/$(dirname "$f")"
  cp -p "$f" "$DEST/$f"
  count=$((count + 1))
done < <(git ls-files -z --cached --others --exclude-standard)
echo "Copied $count files."

cd "$DEST"
git init -q -b main
git add -A
git -c user.name="$NAME" -c user.email="$EMAIL" commit -q -m "KaisenOS: initial public release"
echo "Created a fresh repository with 1 commit."

echo "Scanning the public copy (files + history)..."
if [[ -f "$SRC/.env" ]]; then
  python3 tools/check_public_repo.py --history --env "$SRC/.env"
else
  python3 tools/check_public_repo.py --history
fi
echo "Public copy ready at: $DEST  (not pushed anywhere)"
