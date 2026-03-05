# taskfile

[![PyPI version](https://img.shields.io/pypi/v/taskfile.svg)](https://pypi.org/project/taskfile/)
[![Python version](https://img.shields.io/pypi/pyversions/taskfile.svg)](https://pypi.org/project/taskfile/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Build Status](https://github.com/pyfunc/taskfile/actions/workflows/ci.yml/badge.svg)](https://github.com/pyfunc/taskfile/actions)
[![Codecov](https://codecov.io/gh/pyfunc/taskfile/branch/main/graph/badge.svg)](https://codecov.io/gh/pyfunc/taskfile)
[![Documentation Status](https://readthedocs.org/projects/taskfile/badge/?version=latest)](https://taskfile.readthedocs.io/en/latest/?badge=latest)


**Universal task runner with multi-environment deploy support.**

Write your deploy logic once in `Taskfile.yml`, run it from your terminal, GitLab CI, GitHub Actions, Gitea, Jenkins — or any other pipeline. Zero CI/CD lock-in.

---

## Table of Contents

- [The Problem This Solves](#the-problem-this-solves)
- [Install](#install)
- [Quick Start](#quick-start)
- [Taskfile.yml Reference](#taskfileyml-reference)
- [CLI Commands](#cli-commands)
- [Multi-Environment Deploy](#multi-environment-deploy)
- [Multi-Platform Deploy](#multi-platform-deploy)
- [Environment Groups & Fleet Management](#environment-groups--fleet-management)
- [Parallel Tasks & Error Handling](#parallel-tasks--error-handling)
- [Registry Authentication](#registry-authentication)
- [Multi-Registry Publishing](#multi-registry-publishing)
- [Quadlet Generator](#quadlet-generator)
- [VPS Setup (One-Command)](#vps-setup-one-command)
- [Release Pipeline](#release-pipeline)
- [CI/CD Integration](#cicd-integration)
- [Scaffold Templates](#scaffold-templates)
- [Examples](#examples)

---

## The Problem This Solves

You have one project with multiple deployment stages:

```
local   → Docker Compose + Traefik  (dev on laptop)
staging → Docker Compose over SSH   (test server)
prod    → Podman Quadlet + Traefik  (512MB VPS)
fleet   → 20× Raspberry Pi kiosks   (edge deploy)
```

Without `taskfile`, you maintain separate scripts, CI configs, and fleet tools for each. With `taskfile`:

```
┌──────────────────────────────────────────────────┐
│              Taskfile.yml                        │
│  (environments + tasks + groups = one file)      │
│                                                  │
│  taskfile --env local run dev                    │
│  taskfile --env prod run deploy                  │
│  taskfile -G kiosks run deploy-kiosk             │
│  taskfile fleet status                           │
│  taskfile auth setup                             │
└──────────────────────────────────────────────────┘
```

One YAML file. All environments, platforms, device groups, and deploy tasks in one place.

---

## Install

```bash
pip install taskfile
```

Short alias `tf` is also available after install:

```bash
tf --env prod run deploy
```

---

## Quick Start

```bash
# 1. Create project from template
taskfile init --template full

# 2. See available tasks
taskfile list

# 3. Local development
taskfile --env local run dev

# 4. Deploy to production
taskfile --env prod run deploy

# 5. Dry run — see what would happen
taskfile --env prod --dry-run run deploy
```

---

## Taskfile.yml Reference

A complete `Taskfile.yml` can contain these top-level sections:

```yaml
version: "1"
name: my-project
description: Project description
default_env: local
default_platform: web

# ─── Global variables ────────────────────────────
variables:
  APP_NAME: my-project
  IMAGE: ghcr.io/myorg/my-project
  TAG: latest

# ─── Environments (WHERE to deploy) ──────────────
environments:
  local:
    container_runtime: docker
    compose_command: docker compose
    variables:
      DOMAIN: localhost

  prod:
    ssh_host: prod.example.com
    ssh_user: deploy
    ssh_key: ~/.ssh/id_ed25519
    container_runtime: podman
    service_manager: quadlet
    variables:
      DOMAIN: app.example.com

# ─── Environment Groups (fleet / batch deploy) ───
environment_groups:
  kiosks:
    members: [kiosk-1, kiosk-2, kiosk-3]
    strategy: rolling        # rolling | canary | parallel
    max_parallel: 2

# ─── Platforms (WHAT to deploy) ───────────────────
platforms:
  web:
    desc: Web application
    variables:
      BUILD_DIR: dist/web
  desktop:
    desc: Electron desktop app
    variables:
      BUILD_DIR: dist/desktop

# ─── Tasks ────────────────────────────────────────
tasks:
  build:
    desc: Build the application
    cmds:
      - docker build -t ${IMAGE}:${TAG} .

  deploy:
    desc: Deploy to target environment
    deps: [build, push]          # run dependencies first
    parallel: true               # run deps concurrently
    env: [prod]                  # only run on prod
    platform: [web]              # only run for web platform
    condition: "test -f Dockerfile"  # skip if condition fails
    continue_on_error: true      # don't stop on failure
    retries: 3                   # retry on failure (Ansible-inspired)
    retry_delay: 10              # seconds between retries
    timeout: 300                 # abort after 300 seconds
    tags: [deploy, ci]           # selective execution with --tags
    register: DEPLOY_OUTPUT      # capture stdout into variable
    cmds:
      - "@remote podman pull ${IMAGE}:${TAG}"
      - "@remote systemctl --user restart ${APP_NAME}"
      - "@fn notify Deployed ${APP_NAME}"   # call embedded function
      - "@python print('done')"             # inline Python

# ─── Embedded Functions ───────────────────────────────
functions:
  notify:
    lang: python                 # shell | python | node | binary
    code: |                      # inline code
      import os; print(f"Deployed {os.environ['APP_NAME']}")
  health-check:
    lang: shell
    file: scripts/health.sh      # external file
```

### Key Concepts

- **`environments`** — WHERE to deploy (local machine, remote server via SSH)
- **`platforms`** — WHAT to deploy (web, desktop, mobile)
- **`environment_groups`** — batch of environments for fleet/group deploy
- **`tasks`** — commands to execute, with deps, filters, conditions
- **`variables`** — cascade: global → environment → platform → `--var` CLI overrides
- **`functions`** — embed Python/shell/Node/binary as callable `@fn` from tasks
- **`@remote`** prefix — command runs via SSH on the target environment's host
- **`@fn`** prefix — call an embedded function: `@fn notify arg1`
- **`@python`** prefix — run inline Python: `@python print('hello')`
- **`retries`** / **`timeout`** / **`tags`** / **`register`** — Ansible-inspired robustness
- **`include`** — split Taskfile.yml into multiple files for better organization
- **`pipeline`** — define CI/CD stages for automated generation
- **`compose`** — Docker Compose integration with override support

---

## New Syntax Features

### Embedded Functions

Define reusable functions in Python, Shell, Node.js, or binary executables:

```yaml
functions:
  notify:
    lang: python
    desc: Send Slack notification
    code: |
      import os, json, urllib.request
      webhook = os.environ.get("SLACK_WEBHOOK")
      msg = os.environ.get("FN_ARGS", "Done")
      # ... send notification

  health-check:
    lang: shell
    file: scripts/health.sh  # External file

tasks:
  deploy:
    cmds:
      - "@fn notify Deployment started"
      - "@fn health-check"
```

### Enhanced Task Properties

New Ansible-inspired features for robust automation:

```yaml
tasks:
  deploy:
    desc: Deploy with retry logic
    retries: 3              # Retry on failure
    retry_delay: 10         # Seconds between retries
    timeout: 300            # Abort after 5 minutes
    tags: [deploy, ci]      # Selective execution
    register: DEPLOY_ID     # Capture output
    continue_on_error: true # Don't stop on failure
    cmds:
      - "@fn deploy-service"
      - echo "Deploy ID: {{DEPLOY_ID}}"
```

Run with tags:
```bash
taskfile run --tags deploy  # Only run tasks with 'deploy' tag
```

### Include — Split Taskfile into Multiple Files

Organize large Taskfiles by splitting them:

```yaml
# Taskfile.yml
include:
  - path: ./tasks/build.yml
  - path: ./tasks/deploy.yml
    prefix: deploy    # Tasks become: deploy-local, deploy-prod
  - ./tasks/test.yml  # String shorthand

variables:
  APP: myapp

tasks:
  all:
    deps: [lint, test, build, deploy-prod]
```

```yaml
# tasks/deploy.yml
environments:
  prod:
    ssh_host: prod.example.com

tasks:
  prod:
    cmds: ["@remote systemctl restart myapp"]
```

### Pipeline Section — CI/CD Generation

Define CI/CD stages that generate GitHub Actions, GitLab CI, etc:

```yaml
pipeline:
  python_version: "3.12"
  docker_in_docker: true
  secrets: [GHCR_TOKEN, DEPLOY_KEY]
  cache: [~/.cache/pip, node_modules]
  
  stages:
    - name: test
      tasks: [lint, test]
      cache: [~/.cache/pip]
      
    - name: build
      tasks: [build, push]
      docker_in_docker: true
      
    - name: deploy
      tasks: [deploy]
      env: prod
      when: manual  # or "branch:main"
```

Generate CI configs:
```bash
taskfile ci generate --target github   # GitHub Actions
taskfile ci generate --target gitlab   # GitLab CI
taskfile ci run --stage test          # Run locally
```

### Compose Section — Docker Compose Integration

Enhanced Docker Compose support with overrides:

```yaml
compose:
  file: docker-compose.yml
  override_files:
    - docker-compose.override.yml
    - docker-compose.prod.yml
  network: proxy
  auto_update: true

environments:
  prod:
    compose_file: docker-compose.prod.yml
    env_file: .env.prod
```

---

### Global Options

```
taskfile [OPTIONS] COMMAND [ARGS...]

Options:
  --version                Show version
  -f, --file PATH          Path to Taskfile.yml
  -e, --env ENV            Target environment (default: local)
  -G, --env-group GROUP    Target environment group (fleet deploy)
  -p, --platform PLATFORM  Target platform (e.g. desktop, web)
  --var KEY=VALUE           Override variable (repeatable)
  --dry-run                Show commands without executing
  -v, --verbose            Verbose output
```

### Core Commands

| Command | Description |
|---------|-------------|
| `taskfile <tasks...>` | Run one or more tasks |
| `taskfile <tasks...> --tags ci` | Run only tasks matching tags |
| `taskfile list` | List tasks, environments, groups, platforms, variables |
| `taskfile info <task>` | Show detailed info about a task (incl. tags, retries, timeout) |
| `taskfile validate` | Check Taskfile.yml for errors |
| `taskfile init [--template T]` | Create Taskfile.yml from template |
| `taskfile import <file>` | Import CI/CD config, Makefile, or script INTO Taskfile.yml |
| `taskfile export <format>` | Export Taskfile.yml to other formats (GitHub Actions, GitLab CI) |

### Deploy & Release

| Command | Description |
|---------|-------------|
| `taskfile deploy` | Smart deploy — auto-detects strategy per environment |
| `taskfile release [--tag v1.0]` | Full release pipeline: tag → build → deploy → health |
| `taskfile rollback [--target TAG]` | Rollback to previous version |
| `taskfile setup <IP>` | One-command VPS provisioning + deploy |
| `taskfile version bump` | Bump version (patch/minor/major) |
| `taskfile version show` | Show current version |
| `taskfile version set <version>` | Set specific version |

### Fleet Management

| Command | Description |
|---------|-------------|
| `taskfile fleet status` | SSH health check on all remote environments |
| `taskfile fleet status --group kiosks` | Check only devices in a group |
| `taskfile fleet list` | List remote environments and groups |
| `taskfile fleet repair <env>` | 8-point diagnostics + auto-fix |
| `taskfile -G kiosks run deploy` | Deploy to all devices in a group |

### Registry Auth

| Command | Description |
|---------|-------------|
| `taskfile auth setup` | Interactive token setup for registries |
| `taskfile auth setup --registry pypi` | Setup for one registry only |
| `taskfile auth verify` | Test all configured credentials |

### Infrastructure

| Command | Description |
|---------|-------------|
| `taskfile quadlet generate` | Generate Podman Quadlet from docker-compose.yml |
| `taskfile quadlet upload` | Upload Quadlet files to server via SSH |
| `taskfile ci generate` | Generate CI/CD config (GitHub Actions, GitLab, etc.) |
| `taskfile health` | Check health of deployed services |

### Docker Helpers

| Command | Description |
|---------|-------------|
| `taskfile docker ps` | Show running Docker containers |
| `taskfile docker stop-port <port>` | Stop containers using a specific port |
| `taskfile docker compose-down` | Run `docker compose down` in directory |

---

## Multi-Environment Deploy

Define environments in `Taskfile.yml`, then target them with `--env`:

```bash
# Local development
taskfile --env local run dev

# Staging deploy
taskfile --env staging run deploy

# Production deploy
taskfile --env prod run deploy

# Override variables per-run
taskfile --env prod run deploy --var TAG=v1.2.3 --var DOMAIN=new.example.com
```

### Remote Commands with `@remote`

Any command prefixed with `@remote` runs on the environment's SSH host:

```yaml
tasks:
  restart:
    env: [prod]
    cmds:
      - "@remote systemctl --user restart ${APP_NAME}"
      - "@remote podman ps --filter name=${APP_NAME}"
```

This translates to: `ssh -i ~/.ssh/id_ed25519 deploy@prod.example.com 'systemctl --user restart my-app'`

### Deploy Shortcut

`taskfile deploy` auto-detects the right strategy:

```bash
taskfile --env local deploy    # → docker compose up -d
taskfile --env prod deploy     # → generate Quadlet → scp → systemctl restart
```

---

## Multi-Platform Deploy

Deploy to **desktop** and **web** platforms across environments:

```
┌──────────┬───────────────────────┬──────────────────────────┐
│          │ local                 │ prod                     │
├──────────┼───────────────────────┼──────────────────────────┤
│ desktop  │ npm run dev:electron  │ electron-builder publish │
│ web      │ docker compose up     │ podman pull + restart    │
└──────────┴───────────────────────┴──────────────────────────┘
```

```bash
taskfile --env local --platform desktop run deploy
taskfile --env prod --platform web run deploy
taskfile release    # all platforms at once
```

Variables cascade: **global → environment → platform → CLI overrides**.

Generate a multiplatform scaffold:

```bash
taskfile init --template multiplatform
```

---

## Environment Groups & Fleet Management

Manage fleets of devices (Raspberry Pi, edge nodes, kiosks) using `environment_groups` in `Taskfile.yml`. Each device is an environment with `ssh_host`; groups define batch-deploy strategies.

### Defining a Fleet

```yaml
environments:
  kiosk-lobby:
    ssh_host: 192.168.1.10
    ssh_user: pi
    container_runtime: podman
  kiosk-cafe:
    ssh_host: 192.168.1.11
    ssh_user: pi
    container_runtime: podman
  kiosk-entrance:
    ssh_host: 192.168.1.12
    ssh_user: pi
    container_runtime: podman

environment_groups:
  kiosks:
    members: [kiosk-lobby, kiosk-cafe, kiosk-entrance]
    strategy: rolling       # rolling | canary | parallel
    max_parallel: 2         # for rolling: how many at a time
    canary_count: 1         # for canary: how many to test first
```

### Group Deploy Strategies

- **`rolling`** — deploy to `max_parallel` devices at a time, wait for success, then next batch
- **`canary`** — deploy to `canary_count` devices first, confirm, then deploy to rest
- **`parallel`** — deploy to all devices simultaneously

```bash
# Deploy to all kiosks with rolling strategy
taskfile -G kiosks run deploy-kiosk --var TAG=v2.0

# Deploy to a single device
taskfile --env kiosk-lobby run deploy-kiosk --var TAG=v2.0
```

### Fleet Status & Health

```bash
# Check all remote devices (parallel SSH: temp, RAM, disk, containers, uptime)
taskfile fleet status

# Check only devices in a group
taskfile fleet status --group kiosks

# List all remote environments and groups
taskfile fleet list
```

Example output:

```
┌─────────────────┬──────────────┬────────┬──────┬─────┬──────┬────────────┬─────────┐
│ Name            │ IP           │ Status │ Temp │ RAM │ Disk │ Containers │ Uptime  │
├─────────────────┼──────────────┼────────┼──────┼─────┼──────┼────────────┼─────────┤
│ kiosk-cafe      │ 192.168.1.11 │ ✅ UP  │ 52°C │ 41% │ 23%  │          3 │ up 14d  │
│ kiosk-entrance  │ 192.168.1.12 │ ✅ UP  │ 48°C │ 38% │ 19%  │          3 │ up 14d  │
│ kiosk-lobby     │ 192.168.1.10 │ ✅ UP  │ 55°C │ 45% │ 27%  │          3 │ up 14d  │
└─────────────────┴──────────────┴────────┴──────┴─────┴──────┴────────────┴─────────┘
```

### Fleet Repair

Diagnose and auto-fix issues on a device with 8-point check: ping, SSH, disk, RAM, temperature, Podman, containers, NTP.

```bash
# Interactive repair
taskfile fleet repair kiosk-lobby

# Auto-fix without prompts
taskfile fleet repair kiosk-lobby --auto-fix
```

---

## Parallel Tasks & Error Handling

### Parallel Dependencies

Run task dependencies concurrently for faster builds:

```yaml
tasks:
  deploy:
    deps: [test, lint, build]
    parallel: true              # test, lint, build run at the same time
    cmds:
      - echo "All deps done, deploying..."
```

### Continue on Error

Allow tasks to continue even if a command fails:

```yaml
tasks:
  lint:
    cmds:
      - ruff check .
    continue_on_error: true     # alias for ignore_errors: true

  deploy:
    deps: [lint, test]
    parallel: true
    continue_on_error: true     # failed deps won't stop the deploy
    cmds:
      - "@remote systemctl --user restart ${APP_NAME}"
```

### Conditional Execution

Skip tasks when conditions aren't met:

```yaml
tasks:
  migrate:
    condition: "test -f migrations/pending.sql"
    cmds:
      - "@remote psql < migrations/pending.sql"
```

---

## Registry Authentication

Interactively configure API tokens for package registries. Tokens are saved to `.env` (auto-gitignored).

```bash
# Setup all registries
taskfile auth setup

# Setup one registry
taskfile auth setup --registry pypi

# Verify all configured tokens
taskfile auth verify
```

Supported registries:

| Registry | Token variable | How to get |
|----------|---------------|------------|
| **PyPI** | `PYPI_TOKEN` | https://pypi.org/manage/account/token/ |
| **npm** | `NPM_TOKEN` | `npm token create` |
| **Docker Hub** | `DOCKER_TOKEN` | https://hub.docker.com/settings/security |
| **GitHub** | `GITHUB_TOKEN` | https://github.com/settings/tokens |
| **crates.io** | `CARGO_TOKEN` | https://crates.io/settings/tokens |

---

## Multi-Registry Publishing

Generate a publish scaffold for releasing to multiple registries:

```bash
taskfile init --template publish
```

This creates a `Taskfile.yml` with tasks for:

- **PyPI** — `twine upload`
- **npm** — `npm publish`
- **Docker Hub / GHCR** — `docker push`
- **GitHub Releases** — `gh release create`
- **Landing page** — build & deploy

```bash
# Publish to all registries
taskfile run publish-all --var TAG=v1.0.0

# Publish to single registry
taskfile run publish-pypi --var TAG=v1.0.0
taskfile run publish-docker --var TAG=v1.0.0
```

---

## Quadlet Generator

**Automatically generate Podman Quadlet `.container` files from your existing `docker-compose.yml`.**

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

```bash
# Generate + upload to server
taskfile quadlet generate --env-file .env.prod
taskfile --env prod quadlet upload
```

---

## VPS Setup (One-Command)

Provision a fresh VPS and deploy your app in one command:

```bash
taskfile setup 123.45.67.89 --domain app.example.com
```

This runs:
1. SSH key provisioning
2. System update + Podman install
3. Firewall configuration
4. Deploy user creation
5. Application deployment

Options:

```bash
taskfile setup 123.45.67.89 \
  --domain app.example.com \
  --ssh-key ~/.ssh/custom_key \
  --user admin \
  --ports 80,443,8080

# Dry run
taskfile setup 123.45.67.89 --dry-run

# Skip steps
taskfile setup 123.45.67.89 --skip-provision
taskfile setup 123.45.67.89 --skip-deploy
```

---

## Release Pipeline

Full release orchestration: tag → build → deploy → health check.

```bash
# Full release
taskfile release --tag v1.0.0

# Skip desktop build
taskfile release --tag v1.0.0 --skip-desktop

# Dry run
taskfile release --tag v1.0.0 --dry-run
```

Steps:
1. Create git tag
2. Build desktop applications
3. Build and deploy web (SaaS)
4. Upload desktop binaries
5. Build and deploy landing page
6. Run health checks

### Version Management

Use shorthand commands for version management:

```bash
# Bump version (creates git tag automatically)
taskfile version bump        # 0.1.0 → 0.1.1 (patch)
taskfile version bump minor  # 0.1.0 → 0.2.0
taskfile version bump major  # 0.1.0 → 1.0.0
taskfile version bump --dry-run  # Preview changes

# Show current version
taskfile version show

# Set specific version
taskfile version set 1.0.0
taskfile version set 2.0.0-rc1
```

Rollback:

```bash
taskfile rollback                   # rollback to previous tag
taskfile rollback --target v0.9.0   # rollback to specific tag
taskfile rollback --dry-run
```

---

## CI/CD Integration

Same commands work everywhere — terminal, GitLab CI, GitHub Actions, Jenkins:

```bash
# Terminal
taskfile --env prod run deploy --var TAG=v1.2.3

# GitLab CI
script: taskfile --env prod run deploy --var TAG=$CI_COMMIT_SHORT_SHA

# GitHub Actions
run: taskfile --env prod run deploy --var TAG=${{ github.sha }}

# Jenkins
sh 'taskfile --env prod run deploy --var TAG=${BUILD_NUMBER}'
```

Generate CI configs automatically:

```bash
# Generate GitHub Actions workflow
taskfile ci generate --provider github

# Generated workflows support:
# - Tag-triggered releases (v*)
# - Secrets injection from GitHub Secrets
# - Multi-job pipelines
```

---

## Scaffold Templates

Generate a `Taskfile.yml` from built-in templates:

```bash
taskfile init --template <name>
```

| Template | Description |
|----------|-------------|
| `minimal` | Basic build/deploy, 2 environments |
| `web` | Web app with Docker + Traefik, 3 environments |
| `podman` | Podman Quadlet + Traefik, optimized for low-RAM |
| `full` | All features: multi-env, release, cleanup, quadlet |
| `codereview` | 3-stage: local(Docker) → staging → prod(Podman Quadlet) |
| `multiplatform` | Desktop + Web × Local + Prod deployment matrix |
| `publish` | Multi-registry publishing: PyPI, npm, Docker, GitHub |
| `kubernetes` | Kubernetes + Helm multi-cluster deployment |
| `terraform` | Terraform IaC with multi-environment state management |
| `iot` | IoT/edge fleet with rolling, canary, and parallel strategies |

Templates are stored as plain YAML files and can be customized.

### SSH Embedded (Optional)

For faster, connection-pooled SSH execution without subprocess overhead:

```bash
pip install taskfile[ssh]
```

When `paramiko` is installed, `@remote` commands use native Python SSH with connection pooling. Falls back to subprocess `ssh` automatically if paramiko is not available.

### Include — Split Taskfile into Multiple Files

```yaml
# Taskfile.yml
include:
  - path: ./tasks/build.yml
  - path: ./tasks/deploy.yml
    prefix: deploy              # tasks become: deploy-local, deploy-prod
  - ./tasks/test.yml            # string shorthand
```

Tasks, variables, and environments from included files are merged. Local definitions take precedence.

---

## Project Structure

```
my-project/
├── Taskfile.yml                # tasks, environments, groups
├── docker-compose.yml          # container definitions (source of truth)
├── .env.local                  # local variables
├── .env.prod                   # production variables (gitignored)
├── deploy/
│   └── quadlet/                # auto-generated .container files
└── Dockerfile
```

---

## Examples (24 total)

### Getting Started

| Example | Complexity | Features |
|---------|------------|----------|
| [minimal](examples/minimal/) | ⭐ | test, build, run — no environments |
| [saas-app](examples/saas-app/) | ⭐⭐ | local/staging/prod with pipeline |
| [multiplatform](examples/multiplatform/) | ⭐⭐⭐ | Web + Desktop, CI/CD generation |
| [codereview.pl](examples/codereview.pl/) | ⭐⭐⭐⭐ | 6 CI platforms, Quadlet, docker-compose |

### Publishing

| Example | Registry | Language |
|---------|----------|----------|
| [publish-pypi](examples/publish-pypi/) | PyPI | Python |
| [publish-npm](examples/publish-npm/) | npm | Node.js / TypeScript |
| [publish-cargo](examples/publish-cargo/) | crates.io | Rust |
| [publish-docker](examples/publish-docker/) | GHCR + Docker Hub | any (multi-arch) |
| [publish-github](examples/publish-github/) | GitHub Releases | Go (binaries + checksums) |
| [multi-artifact](examples/multi-artifact/) | 5 registries | Python + Rust + Node.js + Docker |

### Fleet & IoT

| Example | Features |
|---------|----------|
| [fleet-rpi](examples/fleet-rpi/) | 6 RPi, `environment_defaults`, rolling/canary groups |
| [edge-iot](examples/edge-iot/) | IoT gateways, `ssh_port: 2200`, all 3 group strategies, `condition` |

### Infrastructure & Cloud

| Example | Features |
|---------|----------|
| [ci-pipeline](examples/ci-pipeline/) | `pipeline` section, `stage` field, `taskfile ci generate/run/preview`, `condition`, `silent` |
| [kubernetes-deploy](examples/kubernetes-deploy/) | Helm, multi-cluster (staging + prod-eu + prod-us), canary groups |
| [iac-terraform](examples/iac-terraform/) | `dir` (working_dir), `env_file`, Terraform plan/apply/destroy, `condition` |
| [cloud-aws](examples/cloud-aws/) | Lambda + ECS + S3, multi-region, `env_file`, `environment_groups` |
| [quadlet-podman](examples/quadlet-podman/) | `service_manager: quadlet`, `compose` section, `ssh_port: 2222`, `taskfile deploy/setup` |

### Patterns & Import

| Example | Features |
|---------|----------|
| [script-extraction](examples/script-extraction/) | Split Taskfile into shell/Python scripts, mixed inline + script tasks |
| [ci-generation](examples/ci-generation/) | `pipeline` section → 6 CI platforms, stage triggers (`when`), `docker_in_docker` |
| [include-split](examples/include-split/) | `include` — import tasks/vars/envs from other YAML files, prefix support |
| [functions-embed](examples/functions-embed/) | `functions` section, `@fn`/`@python` prefix, retries, timeout, tags, register |
| [import-cicd](examples/import-cicd/) | `taskfile import` — GitHub Actions, GitLab CI, Makefile, shell → Taskfile.yml |

### Advanced / All Features

| Example | Features |
|---------|----------|
| [monorepo-microservices](examples/monorepo-microservices/) | `platforms`, `build_cmd`/`deploy_cmd`, `condition`, `dir`, `stage`, `platform` filter |
| [fullstack-deploy](examples/fullstack-deploy/) | **ALL CLI commands**: deploy, setup, release, init, validate, info, ci, --dry-run |

```bash
# CI pipeline — generate + run locally
cd examples/ci-pipeline
taskfile ci generate --target github
taskfile ci run --stage test

# Kubernetes — multi-cluster canary
cd examples/kubernetes-deploy
taskfile -G all-prod run helm-deploy --var TAG=v1.0.0

# Terraform — multi-env IaC
cd examples/iac-terraform
taskfile --env staging run plan
taskfile --env staging run apply

# IoT fleet — all 3 strategies
cd examples/edge-iot
taskfile -G warehouse run deploy --var TAG=v2.0   # canary
taskfile -G factory run deploy --var TAG=v2.0     # parallel

# AWS — Lambda + ECS multi-region
cd examples/cloud-aws
taskfile --env prod-eu run ecs-deploy lambda-deploy --var TAG=v1.0.0
```

---

## Integration with Other Tools

Taskfile is designed to **complement** existing tools, not replace them all. Here's how to integrate with popular alternatives:

### Taskfile + Make

Use `Makefile` as a thin wrapper for teams that expect `make`:

```makefile
# Makefile — delegates to taskfile
deploy:
	taskfile --env prod run deploy

test:
	taskfile run test

.PHONY: deploy test
```

Or use taskfile alongside Make — each handles what it does best:
- **Make** — C/C++ compilation, file-based dependency graphs
- **Taskfile** — multi-environment deploys, fleet management, registry auth

### Taskfile + Just (casey/just)

Similar philosophy (command runner), different strengths:
- **Just** — simple per-project recipes, no environments
- **Taskfile** — environments, groups, fleet, `@remote`, registry auth

Migration: each Just recipe maps to a Taskfile task. Add `environments` for multi-host.

### Taskfile + Task (go-task.dev)

Both use YAML, but Taskfile adds:
- `environments` / `environment_groups` / `@remote` SSH
- `taskfile fleet`, `taskfile auth`, `taskfile quadlet`
- Publishing pipelines with registry integration

They can coexist — use `Taskfile.yml` for deploy, `Taskfile.dist.yml` for go-task.

### Taskfile + Dagger

Complementary:
- **Dagger** — containerized CI pipelines (build graph in code)
- **Taskfile** — orchestration layer that calls Dagger

```yaml
tasks:
  build:
    cmds:
      - dagger call build --source=.
  deploy:
    deps: [build]
    env: [prod]
    cmds:
      - "@remote podman pull ${IMAGE}:${TAG}"
      - "@remote systemctl --user restart ${APP}"
```

### Taskfile + Ansible

For fleet management at scale:
- **Ansible** — 100+ hosts, complex inventories, roles, idempotent modules
- **Taskfile** — small fleets (<50), simple SSH commands, `environment_groups`

For hybrid: use Ansible for provisioning, Taskfile for daily operations:

```yaml
tasks:
  provision:
    cmds:
      - ansible-playbook -i inventory.yml setup.yml
  deploy:
    cmds:
      - "@remote podman pull ${IMAGE}:${TAG}"
      - "@remote systemctl --user restart ${APP}"
```

---

## Best Practices: Code vs Configuration

### Keep Taskfile.yml declarative

Taskfile.yml is **configuration** — it should declare *what* to do, not *how*:

```yaml
# ✅ Good — declarative, short commands
tasks:
  build:
    deps: [test]
    cmds:
      - cargo build --release

  deploy:
    env: [prod]
    cmds:
      - "@remote podman pull ${IMAGE}:${TAG}"
      - "@remote systemctl --user restart ${APP}"
```

```yaml
# ❌ Bad — logic embedded in YAML
tasks:
  deploy:
    cmds:
      - |
        if [ "$ENV" = "prod" ]; then
          ssh deploy@prod "podman pull $IMAGE"
          ssh deploy@prod "systemctl restart $APP"
        elif [ "$ENV" = "staging" ]; then
          ...
        fi
```

### Extract shell logic to scripts

When a task needs conditionals, loops, or error handling — put it in `scripts/`:

```yaml
# ✅ Taskfile calls script
tasks:
  validate:
    cmds:
      - ./scripts/validate-deploy.sh ${APP_NAME} ${TAG}
```

```bash
# scripts/validate-deploy.sh — testable, lintable, reusable
#!/usr/bin/env bash
set -euo pipefail
docker build -t "$1-validate:$2" .
docker run -d --name "$1-validate" -p 9999:3000 "$1-validate:$2"
curl -sf http://localhost:9999/health || exit 1
```

### Use environment_defaults to reduce duplication

```yaml
# ✅ DRY — shared config in defaults
environment_defaults:
  ssh_user: pi
  ssh_key: ~/.ssh/fleet_ed25519
  container_runtime: podman

environments:
  node-1:
    ssh_host: 192.168.1.10
  node-2:
    ssh_host: 192.168.1.11
```

```yaml
# ❌ WET — repeated on every environment
environments:
  node-1:
    ssh_host: 192.168.1.10
    ssh_user: pi
    ssh_key: ~/.ssh/fleet_ed25519
    container_runtime: podman
  node-2:
    ssh_host: 192.168.1.11
    ssh_user: pi
    ssh_key: ~/.ssh/fleet_ed25519
    container_runtime: podman
```

### Only declare environments you actually use

```yaml
# ✅ No environments needed for a simple publish pipeline
version: "1"
name: my-lib
variables:
  VERSION: "1.0.0"
tasks:
  test:
    cmds: [cargo test]
  publish:
    deps: [test]
    cmds: [cargo publish]
```

```yaml
# ❌ Unnecessary boilerplate
environments:
  local:
    container_runtime: docker
    compose_command: docker compose
# ^ Never used — the tasks don't reference Docker Compose
```

### Use `deps` + `parallel` instead of repeating commands

```yaml
# ✅ Compose via deps
test-all:
  deps: [py-test, rs-test, js-test]
  parallel: true

# ❌ Duplicating commands from other tasks
test-all:
  cmds:
    - cd packages/python && pytest
    - cd packages/rust && cargo test
    - cd packages/node && npm test
```

---

## License

Apache License 2.0 - see [LICENSE](LICENSE) for details.

## Author

Created by **Tom Sapletta** - [tom@sapletta.com](mailto:tom@sapletta.com)
