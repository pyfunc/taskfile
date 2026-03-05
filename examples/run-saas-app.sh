#!/bin/bash
# Run saas-app example - multi-environment SaaS deployment
set -e

cd "$(dirname "$0")/saas-app"

echo "═══════════════════════════════════════════════════════════════"
echo "  SaaS App Example"
echo "═══════════════════════════════════════════════════════════════"

export PYTHONPATH="/home/tom/github/pyfunc/taskfile/src:$PYTHONPATH"

echo ""
echo "▶ taskfile list"
taskfile list 2>/dev/null || python -m taskfile list

echo ""
echo "▶ Environments:"
echo "  - local:   Docker Compose"
echo "  - staging: SSH + Podman Quadlet"
echo "  - prod:    SSH + Podman Quadlet"

echo ""
echo "▶ taskfile --env local list"
taskfile --env local list 2>/dev/null || python -m taskfile --env local list

echo ""
echo "▶ taskfile --env local run lint (dry-run)"
taskfile --env local run lint --dry-run 2>/dev/null || python -m taskfile --env local run lint --dry-run

echo ""
echo "▶ Pipeline stages:"
taskfile ci list 2>/dev/null || python -m taskfile ci list

echo ""
echo "✅ SaaS App example completed"
