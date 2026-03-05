#!/usr/bin/env bash
set -euo pipefail

# Deploy script with multiple functions

build() {
    echo "Building Docker image..."
    docker build -t "${IMAGE:-myapp}:${TAG:-latest}" .
}

test_app() {
    echo "Running tests..."
    pytest tests/ -v
}

deploy_staging() {
    echo "Deploying to staging..."
    ssh deploy@staging.example.com "docker pull ${IMAGE:-myapp}:${TAG:-latest}"
    ssh deploy@staging.example.com "systemctl restart myapp"
}

health_check() {
    echo "Checking health..."
    curl -sf http://staging.example.com/health || exit 1
    echo "Health check passed"
}

# Main
build
test_app
deploy_staging
health_check
