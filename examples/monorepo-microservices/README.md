# Monorepo Microservices — Platforms, Conditions, Working Dirs

4 mikroserwisy (web, api, worker, mobile-bff) w monorepo z platformami i pipeline.

## Features covered

- **`platforms`** — `web`, `api`, `worker`, `mobile-bff` z `build_cmd`/`deploy_cmd`
- **`default_platform`** — domyślna platforma `web`
- **`dir`** (working_dir) — każdy task serwisu działa w swoim `services/X/`
- **`condition`** — test-api/test-worker tylko jeśli istnieje `pyproject.toml`
- **`stage`** — auto-infer pipeline z pól stage na taskach
- **`platform`** filter na build taskach
- **`silent: true`** — logs nie drukuje komendy
- **`compose`** section — `override_files`, `network`, `auto_update`
- **`service_manager: quadlet`** na prod + `compose` na staging
- **`pipeline`** — explicit stages z `docker_in_docker` i `when`

## Usage

```bash
# Lint/test all (parallel)
taskfile run lint-all
taskfile run test-all

# Build + push all images
taskfile run build-all push-all --var TAG=v1.0.0

# Deploy
taskfile --env local run deploy-local
taskfile --env staging run deploy-staging --var TAG=v1.0.0
taskfile --env prod run deploy-prod --var TAG=v1.0.0

# Per-service
taskfile run test-api
taskfile run build-web --var TAG=v1.0.0

# Database
taskfile run db-migrate
taskfile run db-rollback

# CI pipeline
taskfile ci generate --target github
taskfile ci run --stage test
```
