#!/usr/bin/env bash
# Health check with configurable retries and exponential backoff
# Usage: health.sh [URL] [MAX_RETRIES] [INITIAL_DELAY]

URL="${1:-https://${DOMAIN:-localhost}/health}"
MAX_RETRIES="${2:-5}"
DELAY="${3:-2}"

echo "Health check: ${URL} (max ${MAX_RETRIES} retries, ${DELAY}s initial delay)"

for i in $(seq 1 "$MAX_RETRIES"); do
    HTTP_CODE=$(curl -sf -o /dev/null -w "%{http_code}" "$URL" 2>/dev/null)
    if [ "$HTTP_CODE" = "200" ]; then
        echo "✅ Health check passed (attempt ${i}/${MAX_RETRIES})"
        exit 0
    fi
    echo "⏳ Attempt ${i}/${MAX_RETRIES} — HTTP ${HTTP_CODE:-timeout}, retrying in ${DELAY}s..."
    sleep "$DELAY"
    DELAY=$((DELAY * 2))
done

echo "❌ Health check FAILED after ${MAX_RETRIES} attempts"
exit 1
