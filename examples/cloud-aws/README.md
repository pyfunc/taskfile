# Cloud AWS — Lambda + ECS + S3, Multi-Region

Deploy na AWS: ECS (Docker), Lambda (serverless), S3 (static), multi-region (EU + US).

## Features covered

- **`env_file`** — `.env.dev`, `.env.staging`, `.env.prod-eu`, `.env.prod-us`
- **`environment_defaults`** — shared `container_runtime: docker`
- **`environment_groups`** — `all-prod` (canary EU→US), `global` (rolling)
- **`dir`** — Lambda tasks run in `lambda/` directory
- **`condition`** — CDN invalidation only if `CF_DISTRIBUTION_ID` is set
- **`silent: true`** — health check suppresses command echo
- **`pipeline`** — stages with `when: manual` for prod deploy
- **`stage`** field — tasks auto-infer pipeline stages

## Usage

```bash
# Dev
taskfile --env dev run build
taskfile --env dev run ecs-deploy --var TAG=v1.0.0

# Staging (auto on main branch via CI)
taskfile --env staging run ecs-deploy lambda-deploy s3-sync

# Prod — canary (EU first, then US)
taskfile -G all-prod run ecs-deploy --var TAG=v1.0.0

# Lambda
taskfile --env prod-eu run lambda-deploy
taskfile --env prod-eu run lambda-invoke

# Monitoring
taskfile --env prod-eu run ecs-status
taskfile --env prod-eu run ecs-logs
taskfile --env prod-eu run health

# CI pipeline
taskfile ci generate --target github
taskfile ci run
```
