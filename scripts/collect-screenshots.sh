#!/usr/bin/env bash
# Copies the 5 most-recent screenshots from your Desktop into docs/screenshots/
# with the names the README expects.
#
# Take the screenshots first, in THIS order (Cmd+Shift+4, drag over the page):
#   1. Dashboard   2. SQL Workspace   3. Performance Lab
#   4. Customer Analytics   5. AI Analyst
# then run:  ./scripts/collect-screenshots.sh
set -euo pipefail

DEST="$(cd "$(dirname "$0")/.." && pwd)/docs/screenshots"
mkdir -p "$DEST"
NAMES="dashboard sql-workspace performance-lab customer-analytics ai-analyst"

# 5 newest .png on the Desktop, reversed to oldest-first (= the order you took them)
FILES="$(ls -t "$HOME/Desktop/"*.png 2>/dev/null | head -5 | tail -r || true)"
n="$(printf '%s\n' "$FILES" | grep -c . || true)"

if [ "$n" -lt 5 ]; then
  echo "Found $n recent screenshots on your Desktop — need 5."
  echo "Take screenshots of Dashboard, SQL Workspace, Performance Lab,"
  echo "Customer Analytics, AI Analyst (in that order), then re-run this."
  exit 1
fi

i=1
for name in $NAMES; do
  src="$(printf '%s\n' "$FILES" | sed -n "${i}p")"
  cp "$src" "$DEST/$name.png"
  echo "  $name.png  <-  $(basename "$src")"
  i=$((i + 1))
done

echo
echo "Copied 5 screenshots into docs/screenshots/. Next:"
echo "  git add docs/screenshots && git commit -m 'Add app screenshots' && git push"
