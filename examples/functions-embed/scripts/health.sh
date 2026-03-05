#!/usr/bin/env bash
# Health check with retries
set -euo pipefail

URL="${1:-http://localhost:8080/health}"
MAX_RETRIES=5
DELAY=2

for i in $(seq 1 $MAX_RETRIES); do
    if curl -sf "$URL" > /dev/null 2>&1; then
        echo "✅ Health check passed ($URL)"
        exit 0
    fi
    echo "⏳ Attempt $i/$MAX_RETRIES failed, waiting ${DELAY}s..."
    sleep $DELAY
done

echo "❌ Health check failed after $MAX_RETRIES attempts"
exit 1
