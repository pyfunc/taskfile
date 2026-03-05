#!/usr/bin/env bash
# health-check.sh — Health check with retries
# Taskfile calls: ./scripts/health-check.sh
set -euo pipefail

URL="https://${DOMAIN}/health"
MAX_RETRIES=5
RETRY_DELAY=3

echo "Checking ${URL}..."
for i in $(seq 1 ${MAX_RETRIES}); do
    if curl -sf "${URL}" >/dev/null 2>&1; then
        echo "✅ Health OK (attempt ${i}/${MAX_RETRIES})"
        exit 0
    fi
    echo "  Attempt ${i}/${MAX_RETRIES} failed, retrying in ${RETRY_DELAY}s..."
    sleep ${RETRY_DELAY}
done

echo "❌ Health check failed after ${MAX_RETRIES} attempts"
exit 1
