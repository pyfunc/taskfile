#!/usr/bin/env bash
# ci-pipeline.sh — CI pipeline logic extracted from Taskfile.yml
# Taskfile calls: ./scripts/ci-pipeline.sh
set -euo pipefail

echo "=== CI Pipeline ==="

echo "→ Step 1: Lint"
ruff check src/ || true

echo "→ Step 2: Test"
pytest tests/ -v --cov=src/

echo "→ Step 3: Build"
docker build -t "${IMAGE}:${TAG}" .

echo "→ Step 4: Push"
docker push "${IMAGE}:${TAG}"

echo "✅ CI Pipeline complete"
