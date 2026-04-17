#!/usr/bin/env bash
# Demonstrate `taskfile workspace` across three mini-projects.
#
# Exit code: 0 on success, non-zero if any command fails.
# Safe to re-run: `workspace fix` is idempotent; the `projects/` tree is
# restored from git on demand.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECTS="$SCRIPT_DIR/projects"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Ensure taskfile package from this repo is importable without install
export PYTHONPATH="$REPO_ROOT/src:${PYTHONPATH:-}"

TASKFILE=(python3 -m taskfile)

banner() {
  echo
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "  $*"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

banner "1. workspace list — discover projects"
"${TASKFILE[@]}" workspace list --root "$PROJECTS" --depth 1

banner "2. workspace tasks — task frequency across projects"
"${TASKFILE[@]}" workspace tasks --root "$PROJECTS"

banner "3. workspace validate — manifest issues"
"${TASKFILE[@]}" workspace validate --root "$PROJECTS"

banner "4. workspace analyze — per-project analysis"
"${TASKFILE[@]}" workspace analyze --root "$PROJECTS"

banner "5. workspace compare — peer benchmark (stdout summary)"
"${TASKFILE[@]}" workspace compare -r "$PROJECTS"

banner "6. workspace compare -o CSV"
"${TASKFILE[@]}" workspace compare -r "$PROJECTS" -o "$SCRIPT_DIR/report.csv"
echo
echo "CSV header:"
head -1 "$SCRIPT_DIR/report.csv"
echo
echo "CSV rows:"
wc -l < "$SCRIPT_DIR/report.csv"

banner "7. workspace run build --dry-run"
"${TASKFILE[@]}" workspace run build --root "$PROJECTS" --dry-run

banner "8. workspace fix --dry-run (preview repairs)"
"${TASKFILE[@]}" workspace fix --root "$PROJECTS" --dry-run

echo
echo "✅ workspace example completed successfully"
echo "   CSV report: $SCRIPT_DIR/report.csv"
