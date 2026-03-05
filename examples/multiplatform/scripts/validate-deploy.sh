#!/usr/bin/env bash
set -euo pipefail
# Validate deployment in isolated Docker container.
# Usage: ./scripts/validate-deploy.sh [APP_NAME] [TAG]

APP_NAME="${1:-my-app}"
TAG="${2:-latest}"
CONTAINER="${APP_NAME}-validate"

echo "🧪 Validating deployment in Docker..."
docker build -t "${CONTAINER}:${TAG}" -f Dockerfile .
docker run -d --name "${CONTAINER}" -p 9999:3000 "${CONTAINER}:${TAG}"

echo "⏳ Waiting for container..."
sleep 5

if curl -sf http://localhost:9999/health; then
  echo "✅ Health check passed"
  docker stop "${CONTAINER}" && docker rm "${CONTAINER}"
else
  echo "❌ Health check failed"
  docker logs "${CONTAINER}"
  docker stop "${CONTAINER}" && docker rm "${CONTAINER}"
  exit 1
fi
