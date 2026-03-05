#!/bin/bash
# Run minimal example - basic task runner functionality
set -e

cd "$(dirname "$0")/minimal"

echo "═══════════════════════════════════════════════════════════════"
echo "  Minimal Example"
echo "═══════════════════════════════════════════════════════════════"

export PYTHONPATH="/home/tom/github/pyfunc/taskfile/src:$PYTHONPATH"

echo ""
echo "▶ taskfile --version"
taskfile --version 2>/dev/null || python -m taskfile --version

echo ""
echo "▶ taskfile list"
taskfile list 2>/dev/null || python -m taskfile list

echo ""
echo "▶ taskfile run test (dry-run)"
taskfile run test --dry-run 2>/dev/null || python -m taskfile run test --dry-run

echo ""
echo "▶ taskfile run build (dry-run)"
taskfile run build --dry-run 2>/dev/null || python -m taskfile run build --dry-run

echo ""
echo "✅ Minimal example completed"
