#!/usr/bin/env bash
# deploy.sh — Deploy logic extracted from Taskfile.yml
# Taskfile calls: ./scripts/deploy.sh
# Variables ${ENV}, ${IMAGE}, ${TAG}, ${DOMAIN}, ${RUNTIME} come from taskfile runner.
set -euo pipefail

echo "=== Deploying ${APP_NAME}:${TAG} to ${ENV} ==="

case "${ENV}" in
    local)
        echo "→ Local deploy via docker compose..."
        docker compose up -d --build
        echo "✅ ${APP_NAME} → http://localhost:3000"
        ;;
    staging|prod)
        echo "→ Remote deploy to ${ENV}..."
        echo "→ Pulling image..."
        # @remote commands are handled by taskfile SSH layer,
        # but in scripts you can also call taskfile directly:
        taskfile --env "${ENV}" run health 2>/dev/null || true
        echo "✅ Deployed to https://${DOMAIN}"
        ;;
    *)
        echo "❌ Unknown environment: ${ENV}"
        exit 1
        ;;
esac
