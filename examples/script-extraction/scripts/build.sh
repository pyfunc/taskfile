#!/usr/bin/env bash
# build.sh — Complex build logic extracted from Taskfile.yml
# Taskfile calls: ./scripts/build.sh
# Variables ${IMAGE}, ${TAG} are passed via environment by taskfile runner.
set -euo pipefail

echo "=== Building ${IMAGE}:${TAG} ==="

# Multi-stage: lint check before build
if command -v hadolint &>/dev/null; then
    echo "→ Linting Dockerfile..."
    hadolint Dockerfile || true
fi

# Build with cache
echo "→ Building Docker image..."
docker build \
    --build-arg BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --build-arg VERSION="${TAG}" \
    --label "org.opencontainers.image.created=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --label "org.opencontainers.image.version=${TAG}" \
    -t "${IMAGE}:${TAG}" \
    -t "${IMAGE}:latest" \
    .

echo "→ Image size: $(docker image inspect "${IMAGE}:${TAG}" --format='{{.Size}}' | numfmt --to=iec 2>/dev/null || echo 'unknown')"
echo "✅ Build complete: ${IMAGE}:${TAG}"
