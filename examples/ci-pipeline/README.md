# CI Pipeline — Stages, Generate, Run Locally

Demonstrates the `pipeline` section and `taskfile ci` commands.

## Features covered

- **`pipeline`** section with explicit stages, `when`, `docker_in_docker`, `artifacts`, `cache`
- **`stage`** field on tasks (auto-infer pipeline from tasks)
- **`condition`** — run task only if Docker is available
- **`silent`** — suppress command echo
- **`env_file`** — per-environment `.env` files
- **`taskfile ci generate`** — generate GitHub Actions, GitLab CI, etc.
- **`taskfile ci run`** — run pipeline locally
- **`taskfile ci preview`** — preview generated config

## Pipeline

```
lint (ruff, mypy, pip-audit, bandit)
  → test (unit + integration with Docker)
    → build (docker build + push to GHCR)
      → deploy-staging (auto on develop branch)
        → deploy-prod (manual approval)
```

## Usage

```bash
# Generate CI configs from pipeline section
taskfile ci generate --target github    # → .github/workflows/taskfile.yml
taskfile ci generate --target gitlab    # → .gitlab-ci.yml
taskfile ci generate --all              # all 6 platforms

# Preview without writing files
taskfile ci preview --target github

# Run pipeline locally (same stages as CI)
taskfile ci run                         # full pipeline
taskfile ci run --stage test            # only test stage
taskfile ci run --skip deploy-prod      # all except prod deploy
taskfile ci run --stop-at build         # lint → test → build, skip deploy

# Run individual tasks
taskfile run test
taskfile --env staging run deploy-staging
taskfile --env prod run deploy-prod --dry-run

# List pipeline stages
taskfile ci list
```

## Key concepts

- **`when: manual`** — deploy-prod requires manual approval in CI
- **`when: "branch:develop"`** — deploy-staging auto-triggers on develop
- **`docker_in_docker: true`** — build stage gets Docker access in CI
- **`condition`** — integration tests only run if Docker is available
- **`silent: true`** — health-check doesn't print the curl command
