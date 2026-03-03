# taskfile


**Universal task runner with multi-environment deploy support.**

Write your deploy logic once in `Taskfile.yml`, run it from your terminal, GitLab CI, GitHub Actions, Gitea, Jenkins — or any other pipeline. Zero CI/CD lock-in.

## The Problem This Solves

You have one project (`codereview.pl`) with deployment stages:

```
local   → Docker Compose + Traefik  (dev on laptop)
prod    → Podman Quadlet + Traefik  (512MB VPS)
```

Without `taskfile`, you maintain separate configs for each. With `taskfile`:

```
┌─────────────────────────────────────────────┐
│         docker-compose.yml                  │
│         (single source of truth)            │
│                                             │
│  .env.local    →  docker compose up         │
│  .env.prod     →  generate Quadlet → deploy │
└─────────────────────────────────────────────┘
```

One compose file, `.env` files for differences, automatic Quadlet generation.

## Install

```bash
pip install taskfile
```

## Quick Start

```bash
# Create project from template
taskfile init --template codereview

# See available tasks
taskfile list

# Local development
taskfile --env local run dev

# Deploy to production (generates Quadlet, uploads, restarts)
taskfile --env prod run deploy

# Or use the deploy shortcut (auto-detects strategy)
taskfile --env prod deploy

# Dry run — see what would happen
taskfile --env prod --dry-run deploy
```

Short alias `tf` is also available:

```bash
tf --env prod run deploy-quick
```

## How It Works

### Project Structure

```
my-project/
├── docker-compose.yml          # SINGLE SOURCE OF TRUTH
├── .env.local                  # local: localhost, no TLS, relaxed limits
├── .env.prod                   # prod: TLS, tight limits
├── Taskfile.yml                # all deploy tasks
├── deploy/
│   └── quadlet/                # auto-generated .container files
└── Dockerfile
```

### docker-compose.yml — Same File, All Environments

All differences between environments are captured in variables:

```yaml
services:
  app:
    image: ${REGISTRY}/my-app:${TAG:-latest}
    labels:
      traefik.http.routers.app.rule: "Host(`${DOMAIN:-app.localhost}`)"
      traefik.http.routers.app.tls: "${TLS_ENABLED:-false}"
    deploy:
      resources:
        limits:
          memory: ${APP_MEMORY:-128m}
```

### Deploy Commands

```bash
# Local development
taskfile --env local run dev          # docker compose up --build
taskfile --env local run dev-logs     # follow logs

# Production deploy
taskfile --env prod run deploy        # full: build → push → quadlet → upload → restart
taskfile --env prod run deploy-quick  # just: pull → restart
taskfile --env prod run deploy-service --var SVC=app

# Quadlet generation
taskfile quadlet generate --env-file .env.prod
taskfile --env prod quadlet upload

# Operations
taskfile --env prod run status
taskfile --env prod run logs --var SVC=app
taskfile --env prod run ram
```

## Quadlet Generator

The killer feature: **automatically generate Podman Quadlet `.container` files from your existing `docker-compose.yml`**.

```bash
taskfile quadlet generate --env-file .env.prod -o deploy/quadlet
```

Reads `docker-compose.yml`, resolves `${VAR:-default}` with `.env.prod` values, generates Quadlet units with:

- `[Container]` — image, env, volumes, labels, ports, resource limits
- `[Unit]` — `After=/Requires=` from `depends_on`
- `AutoUpdate=registry` for automatic updates
- Traefik labels preserved
- Named volumes → `.volume` units
- Networks → `.network` units

No `podlet` binary needed — pure Python.

## Deploy Shortcut

`taskfile deploy` auto-detects the right strategy:

```bash
taskfile --env local deploy    # → docker compose up -d
taskfile --env prod deploy     # → generate Quadlet → scp → systemctl restart
```

## Key Features

- **Multi-env deploy** — local/staging/prod with different runtimes
- **`@remote` prefix** — commands run via SSH on target server
- **Variable substitution** — `${VAR}`, `{{VAR}}`, cascading: global → env → CLI → OS
- **Task dependencies** — `deps: [test, push, generate]`
- **Environment filters** — `env: [prod]` restricts task to specific envs
- **Conditional execution** — `condition: "test -f migrations/pending.sql"`
- **Dry run** — `--dry-run` shows commands without executing

## CI/CD Integration

Same command everywhere:

```bash
# Terminal
taskfile --env prod run deploy --var TAG=v1.2.3

# GitLab CI
script: taskfile --env prod run deploy --var TAG=$CI_COMMIT_SHORT_SHA

# GitHub Actions
run: taskfile --env prod run deploy --var TAG=${{ github.sha }}
```

## CLI Reference

```
taskfile run <tasks...>          Run one or more tasks
taskfile list                    List tasks and environments
taskfile init                    Create Taskfile.yml
taskfile validate                Check for errors
taskfile info <task>             Show task details
taskfile deploy                  Smart deploy (auto-detects strategy)
taskfile quadlet generate        Generate Quadlet from docker-compose.yml
taskfile quadlet upload          Upload Quadlet files to server

Options:
  -e, --env ENV             Target environment (default: local)
  -f, --file PATH           Path to Taskfile.yml
  --var KEY=VALUE            Override variable (repeatable)
  --dry-run                 Show commands without executing
  -v, --verbose             Verbose output

Templates: minimal | web | podman | codereview | full
```

## License

Apache License 2.0 - see [LICENSE](LICENSE) for details.

## Author

Created by **Tom Sapletta** - [tom@sapletta.com](mailto:tom@sapletta.com)
