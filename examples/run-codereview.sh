#!/bin/bash
# Run codereview.pl example - real-world production deployment
set -e

cd "$(dirname "$0")/codereview.pl"

echo "═══════════════════════════════════════════════════════════════"
echo "  codereview.pl Example (Real-World Production)"
echo "═══════════════════════════════════════════════════════════════"

export PYTHONPATH="/home/tom/github/pyfunc/taskfile/src:$PYTHONPATH"

echo ""
echo "▶ taskfile list"
taskfile list 2>/dev/null || python3 -m taskfile list

echo ""
echo "▶ Environments:"
echo "  - local: Docker + Traefik"
echo "  - prod:  Podman Quadlet + Traefik"

echo ""
echo "▶ Pipeline:"
taskfile ci list 2>/dev/null || python3 -m taskfile ci list

echo ""
echo "▶ Available CI/CD targets:"
taskfile ci targets 2>/dev/null || python3 -m taskfile ci targets

echo ""
echo "▶ Generate CI configs (dry-run):"
taskfile --dry-run ci generate --target github 2>/dev/null || python3 -m taskfile --dry-run ci generate --target github

echo ""
echo "✅ codereview.pl example completed"
echo ""
echo "📦 CI/CD files present:"
ls -la .github/workflows/ 2>/dev/null || echo "  (no .github/workflows)"
ls -la .gitea/ 2>/dev/null || echo "  (no .gitea)"
ls -la .drone.yml 2>/dev/null && echo "  - .drone.yml"
ls -la Jenkinsfile 2>/dev/null && echo "  - Jenkinsfile"
ls -la Makefile 2>/dev/null && echo "  - Makefile"
