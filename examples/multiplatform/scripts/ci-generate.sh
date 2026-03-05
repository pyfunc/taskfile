#!/usr/bin/env bash
set -euo pipefail
# Generate CI/CD pipeline configs for GitHub Actions and GitLab CI.
# Usage: ./scripts/ci-generate.sh

mkdir -p .github/workflows

cat > .github/workflows/deploy.yml << 'EOF'
name: Deploy
on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Taskfile
        run: pip install taskfile
      - name: Deploy to production
        run: taskfile --env prod --platform web run deploy
        env:
          VPS_IP: ${{ secrets.VPS_IP }}
          VPS_USER: ${{ secrets.VPS_USER }}
          VPS_SSH_KEY: ${{ secrets.VPS_SSH_KEY }}
EOF

cat > .gitlab-ci.yml << 'EOF'
stages: [build, deploy]

variables:
  VPS_IP: $VPS_IP
  VPS_USER: $VPS_USER

build:
  stage: build
  script:
    - pip install taskfile
    - taskfile run build-web
  artifacts:
    paths: [dist/]

deploy:
  stage: deploy
  script:
    - taskfile --env prod --platform web run deploy
  only: [main]
EOF

echo "✅ Generated: .github/workflows/deploy.yml, .gitlab-ci.yml"
