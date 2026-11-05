#!/usr/bin/env bash
# Update an existing public copy (made by export_public.sh) with the
# current project, as one new commit. Nothing is pushed.
#
#   tools/update_public.sh ~/Desktop/KaisenOS-public "Describe the change"
#
# Same rules as export_public.sh: only project files, minus personal
# material, and the result must pass the safety scan before it's
# committed. Then review and push from the public folder yourself
# (git push), or ask for it to be pushed.

set -euo pipefail
SRC="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${1:?usage: tools/update_public.sh <public-folder> <commit message>}"
MSG="${2:?usage: tools/update_public.sh <public-folder> <commit message>}"
EXCLUDE_RE='^(Fitness/workouts/|Fitness/knowledge/.*\.pdf$|Fitness/data/|.*\.(db|sqlite|sqlite3|log|xlsx|xls)$|\.env$|.*/\.env$|\.claude/settings\.local\.json$)'

[[ -d "$DEST/.git" ]] || { echo "Not a git repository: $DEST (use export_public.sh first)"; exit 1; }
[[ -z "$(git -C "$DEST" status --porcelain)" ]] || { echo "The public copy has uncommitted changes; resolve those first."; exit 1; }

# Start from an empty tree (tracked files only; build output and venvs stay).
git -C "$DEST" ls-files -z | (cd "$DEST" && xargs -0 rm -f)

cd "$SRC"
count=0
while IFS= read -r -d '' f; do
  [[ -f "$f" ]] || continue
  if [[ "$f" =~ $EXCLUDE_RE ]]; then continue; fi
  mkdir -p "$DEST/$(dirname "$f")"
  cp -p "$f" "$DEST/$f"
  count=$((count + 1))
done < <(git ls-files -z --cached --others --exclude-standard)

cd "$DEST"
find . -type d -empty -not -path "./.git/*" -delete 2>/dev/null || true
git add -A
if git diff --cached --quiet; then echo "No changes."; exit 0; fi

ENV_ARGS=()
[[ -f "$SRC/.env" ]] && ENV_ARGS=(--env "$SRC/.env")

echo "Scanning before commit..."
python3 tools/check_public_repo.py "${ENV_ARGS[@]+"${ENV_ARGS[@]}"}"

git commit -q -m "$MSG"
python3 tools/check_public_repo.py --history "${ENV_ARGS[@]+"${ENV_ARGS[@]}"}" >/dev/null 2>&1 || {
  echo "History scan failed after commit. Undoing the commit."; git reset -q --soft HEAD~1; exit 1; }
echo "Committed $count files as: $MSG"
git log --oneline -1
echo "Not pushed. To publish: cd $DEST && git push"
