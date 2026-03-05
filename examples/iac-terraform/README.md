# IaC Terraform — Multi-Environment Infrastructure

Terraform IaC z multi-environment (dev/staging/prod/prod-us), plan/apply/destroy.

## Features covered

- **`dir`** (working_dir) — all tasks run inside `terraform/` directory
- **`env_file`** — per-environment `.env` files for AWS credentials
- **`condition`** — cost estimation only if infracost is installed
- **`environment_groups`** — `all-prod` for rolling infra updates
- **`stage`** field — `ci-plan` and `ci-apply` for CI pipeline inference
- **`ignore_errors`** — lint/security don't block the pipeline
- **`deps` + `parallel`** — validate + lint run in parallel before plan

## Usage

```bash
# Dev environment
taskfile --env dev run plan
taskfile --env dev run apply

# Staging
taskfile --env staging run plan
taskfile --env staging run apply

# Prod (EU + US rolling)
taskfile -G all-prod run plan
taskfile -G all-prod run apply

# Inspect
taskfile --env prod run output
taskfile --env prod run state-list
taskfile --env dev run cost

# Security scan
taskfile run lint
taskfile run security

# Destroy dev (careful!)
taskfile --env dev run destroy
```
