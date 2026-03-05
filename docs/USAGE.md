# Taskfile - Usage Guide

Complete guide to using taskfile CLI and Taskfile.yml format.

## Installation

```bash
pip install taskfile
```

For SSH support:
```bash
pip install taskfile[paramiko]
```

## Quick Start

### 1. Create a Taskfile

```bash
taskfile init                    # Create from template
taskfile init -i                 # Interactive with choices
taskfile init --template web     # Specific template
```

### 2. Run Tasks

```bash
taskfile list                    # Show all tasks
taskfile run build               # Run single task
taskfile run build test deploy   # Run multiple tasks
taskfile run deploy --env prod   # With environment
```

### 3. Interactive Setup

```bash
taskfile doctor                  # Check project health
taskfile setup env               # Configure .env interactively
taskfile setup hosts             # Configure deployment hosts
```

## CLI Reference

### Core Commands

| Command | Description | Example |
|---------|-------------|---------|
| `init` | Create Taskfile.yml | `taskfile init -i` |
| `list` | List tasks & environments | `taskfile list` |
| `run` | Run one or more tasks | `taskfile run build` |
| `info` | Show task details | `taskfile info deploy` |
| `validate` | Validate Taskfile | `taskfile validate` |
| `import` | Import from other format | `taskfile import Makefile` |
| `export` | Export to other format | `taskfile export github-actions` |

### Interactive Commands

| Command | Description | Example |
|---------|-------------|---------|
| `doctor` | Diagnose project | `taskfile doctor --fix` |
| `setup env` | Configure environment | `taskfile setup env` |
| `setup hosts` | Configure hosts | `taskfile setup hosts` |

### Development Commands

| Command | Description | Example |
|---------|-------------|---------|
| `watch` | Watch files & auto-run | `taskfile watch build` |
| `cache show` | Show cache stats | `taskfile cache show` |
| `cache clear` | Clear cache | `taskfile cache clear build` |
| `graph` | Visualize dependencies | `taskfile graph --dot` |

### Import/Export

| Command | Description | Example |
|---------|-------------|---------|
| `import` | Import from other format | `taskfile import Makefile` |
| `export` | Export to other format | `taskfile export github-actions` |
| `detect` | Detect config files | `taskfile detect` |

### CI/CD Commands

| Command | Description | Example |
|---------|-------------|---------|
| `ci generate` | Generate CI config | `taskfile ci generate --target github` |
| `ci run` | Run CI pipeline locally | `taskfile ci run --stage test` |
| `ci preview` | Preview CI config | `taskfile ci preview --target gitlab` |

### Package Management

| Command | Description | Example |
|---------|-------------|---------|
| `pkg search` | Search packages | `taskfile pkg search docker` |
| `pkg install` | Install package | `taskfile pkg install user/tasks` |
| `pkg list` | List installed | `taskfile pkg list` |
| `pkg uninstall` | Remove package | `taskfile pkg uninstall tasks` |

### Deploy Commands

| Command | Description | Example |
|---------|-------------|---------|
| `deploy` | Smart deploy with auto-strategy | `taskfile deploy --env prod` |
| `release` | Full release pipeline | `taskfile release --tag v1.0.0` |
| `rollback` | Rollback deployment | `taskfile rollback --target v0.9.0` |
| `setup` | VPS provisioning | `taskfile setup 123.45.67.89` |

### Fleet Management

| Command | Description | Example |
|---------|-------------|---------|
| `fleet status` | Check fleet health | `taskfile fleet status` |
| `fleet list` | List environments | `taskfile fleet list` |
| `fleet repair` | Diagnose and fix | `taskfile fleet repair node-1` |

### Registry & Auth

| Command | Description | Example |
|---------|-------------|---------|
| `auth setup` | Configure registry tokens | `taskfile auth setup` |
| `auth verify` | Test credentials | `taskfile auth verify` |

### Quadlet Generation

| Command | Description | Example |
|---------|-------------|---------|
| `quadlet generate` | Generate from compose | `taskfile quadlet generate` |
| `quadlet upload` | Upload to server | `taskfile quadlet upload --env prod` |

### Web UI

```bash
taskfile serve              # Start dashboard on :8080
taskfile serve -p 3000     # Custom port
taskfile serve --no-browser # Don't open browser
```

## Taskfile.yml Format

### Basic Structure

```yaml
version: "1"
name: my-project
description: Project description

variables:
  VERSION: "1.0.0"
  IMAGE: myapp

environments:
  local:
    container_runtime: docker
  prod:
    ssh_host: ${PROD_HOST}
    ssh_user: deploy

tasks:
  build:
    desc: Build application
    cmds:
      - docker build -t ${IMAGE}:${VERSION} .
  
  deploy:
    desc: Deploy to production
    env: [prod]
    deps: [build, test]
    cmds:
      - "@remote docker pull ${IMAGE}:${VERSION}"
      - "@remote docker-compose up -d"
```

### Task Properties

| Property | Type | Description |
|----------|------|-------------|
| `desc` | string | Task description |
| `cmds` | list | Commands to execute |
| `deps` | list | Dependencies (run first) |
| `env` | list | Allowed environments |
| `platform` | list | Allowed platforms |
| `condition` | string | Skip if condition false |
| `parallel` | bool | Run deps in parallel |
| `ignore_errors` | bool | Continue on failure |
| `retries` | int | Retry attempts |
| `retry_delay` | int | Seconds between retries |
| `timeout` | int | Seconds before timeout |
| `tags` | list | For selective execution |
| `silent` | bool | Suppress output |
| `register` | string | Capture output to variable |

### Special Command Prefixes

| Prefix | Description | Example |
|--------|-------------|---------|
| `@fn` | Call embedded function | `@fn notify "Done"` |
| `@python` | Inline Python | `@python print('hello')` |
| `@remote` | SSH execution | `@remote docker ps` |

### New Task Properties

| Property | Type | Description |
|----------|------|-------------|
| `retries` | int | Retry attempts on failure |
| `retry_delay` | int | Seconds between retries |
| `timeout` | int | Max execution time in seconds |
| `tags` | list | Tags for selective execution |
| `register` | string | Capture output to variable |
| `continue_on_error` | bool | Continue on failure |
| `stage` | string | CI/CD stage assignment |
| `dir` | string | Working directory |

### Running with Tags

```bash
# Run only tasks with specific tags
taskfile run --tags deploy
taskfile run --tags ci,deploy

# Combine with environment
taskfile --env prod run --tags deploy
```

### Embedded Functions

Define functions in your Taskfile:

```yaml
functions:
  notify:
    lang: python
    code: |
      import os
      msg = os.environ.get('FN_ARGS', 'Done')
      print(f"Notification: {msg}")

tasks:
  deploy:
    cmds:
      - "@fn notify Deployment started"
      - echo "Deploying..."
      - "@fn notify Deployment complete"
```

### Include External Files

Split your Taskfile:

```yaml
# Taskfile.yml
include:
  - path: ./tasks/build.yml
  - path: ./tasks/deploy.yml
    prefix: deploy

# tasks/deploy.yml
tasks:
  prod:
    cmds: ["@remote systemctl restart app"]
```

### Pipeline Configuration

Define CI/CD stages:

```yaml
pipeline:
  docker_in_docker: true
  secrets: [GHCR_TOKEN]
  
  stages:
    - name: test
      tasks: [lint, test]
    - name: deploy
      tasks: [deploy]
      when: manual
```

Generate CI:
```bash
taskfile ci generate --target github
taskfile ci run --stage test
```

## Tips & Tricks

### Use Environment Variables

```yaml
variables:
  API_KEY: ${API_KEY:-default_value}
```

### Conditional Execution

```yaml
tasks:
  deploy:
    condition: "${DEPLOY_ENABLED} == true"
    cmds:
      - echo "Deploying..."
```

### Parallel Dependencies

```yaml
tasks:
  build-all:
    desc: Build everything
    deps: [build-web, build-api, build-worker]
    parallel: true
```

### Capture Output

```yaml
tasks:
  get-version:
    cmds:
      - cat package.json | grep version
    register: VERSION
  
  print-version:
    deps: [get-version]
    cmds:
      - echo "Version is {{VERSION}}"
```

## Common Workflows

### Development

```bash
# Start with watch mode
taskfile watch build

# Run tests on change
taskfile watch -p src test
```

### Deployment

```bash
# Setup once
taskfile setup hosts

# Deploy to staging
taskfile run deploy --env staging

# Deploy to production
taskfile run deploy --env prod
```

### CI/CD

```bash
# Generate CI config
taskfile run ci-generate

# Or export to GitHub Actions
taskfile export github-actions -o .github/workflows/ci.yml
```

## Troubleshooting

### Task Not Found

```bash
taskfile list              # See available tasks
taskfile doctor            # Diagnose issues
```

### SSH Issues

```bash
# Test SSH connection
taskfile setup hosts       # Configure hosts
taskfile validate          # Validate config
```

### Cache Problems

```bash
taskfile cache clear       # Clear all cache
taskfile cache show        # Check cache stats
```

## Next Steps

- Read [Taskfile Format Reference](FORMAT.md)
- See [Feature Details](FEATURES.md)
- Compare with other tools [Comparisons](COMPARISONS.md)
