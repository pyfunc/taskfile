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
taskfile --version 2>/dev/null || python3 -m taskfile --version

echo ""
echo "▶ taskfile list"
taskfile list 2>/dev/null || python3 -m taskfile list

echo ""
echo "▶ taskfile run test (dry-run)"
taskfile --dry-run run test 2>/dev/null || python3 -m taskfile --dry-run run test

echo ""
echo "▶ taskfile run build (dry-run)"
taskfile --dry-run run build 2>/dev/null || python3 -m taskfile --dry-run run build

echo ""
echo "✅ Minimal example completed"
