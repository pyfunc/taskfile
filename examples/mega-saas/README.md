# mega-saas — Ultimate Taskfile Example

The **most complex** example in this repository. Demonstrates every Taskfile feature in a single, realistic SaaS project setup.

## Features Used

| Feature | Usage |
|---------|-------|
| **variables** | 16 global variables with `${VAR:-default}` fallbacks |
| **environments** | 7 environments: local, staging, 3× prod regions, 2× edge CDN |
| **environment_groups** | 4 groups: `all-prod` (canary), `prod-west` (rolling), `all-edge` (parallel), `global` (rolling) |
| **platforms** | 3 platforms: web, desktop, mobile-api |
| **compose** | Docker Compose with override files and network config |
| **include** | 2 included sub-files with prefix namespacing |
| **functions** | 7 embedded functions: Python (3), Shell (2), Node.js (1), Binary (1) |
| **pipeline** | 7 CI/CD stages with secrets, cache, artifacts, docker-in-docker |
| **tasks** | 50+ tasks covering lint, test, build, push, deploy, rollback, ops, DB, CDN |
| **@remote** | SSH commands for remote execution |
| **@fn** | Embedded function calls (notify, health-check, sentry-release, etc.) |
| **@python** | Inline Python execution |
| **retries / retry_delay** | Ansible-inspired retry logic on deploy and smoke tasks |
| **timeout** | Command timeouts on tests, provisioning, deploy |
| **tags** | Selective execution: ci, deploy, ops, maintenance, etc. |
| **register** | Capture stdout into variables (BUILD_API_SHA, CURRENT_VERSION, etc.) |
| **condition** | Skip tasks based on shell conditions |
| **deps + parallel** | Task dependencies with concurrent execution |
| **stage** | Pipeline stage assignment for CI generation |
| **env / platform filter** | Restrict tasks to specific environments/platforms |
| **dir** | Working directory override per task |
| **silent** | Suppress command echo |
| **ignore_errors** | Continue on failure (lint tasks) |
| **default_env / default_platform** | Global defaults |

## Structure

```
mega-saas/
├── Taskfile.yml              # Main taskfile (this file)
├── tasks/
│   ├── monitoring.yml        # Included: mon-* tasks
│   └── database.yml          # Included: db-* tasks (extra)
└── scripts/
    ├── health.sh             # External shell function
    └── report.py             # External Python function
```

## Example Commands

```bash
# Local development
taskfile dev
taskfile dev-logs

# Run CI locally
taskfile ci-run-local
taskfile --tags ci run lint test-unit build-all

# Deploy to staging
taskfile --env staging run deploy-compose

# Canary deploy to production (1 region first, then all)
taskfile -G all-prod run deploy-quadlet

# Rolling deploy to EU + US only
taskfile -G prod-west run deploy-quick

# Deploy edge CDN nodes in parallel
taskfile -G all-edge run deploy-edge

# Single region deploy
taskfile --env prod-eu run deploy-quadlet

# Quick deploy (skip Quadlet regen)
taskfile --env prod-us run deploy-quick --var TAG=v1.2.3

# Rollback
taskfile --env prod-eu run rollback --var TAG=v1.2.2

# Operations
taskfile -G all-prod run health
taskfile --env prod-eu run logs --var SVC=api
taskfile -G all-prod run ram
taskfile -G all-prod run cleanup

# Fleet management
taskfile fleet status --group all-prod
taskfile fleet repair prod-eu

# Database
taskfile run db-migrate
taskfile --env prod-eu run db-backup

# Generate CI configs
taskfile ci generate --all
taskfile ci preview --target github

# Dry run
taskfile --env prod-eu --dry-run run deploy-quadlet

# Validate
taskfile validate
```
