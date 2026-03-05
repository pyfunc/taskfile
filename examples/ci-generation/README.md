# CI Generation — Generate CI/CD for 6 Platforms

Generowanie konfiguracji CI/CD z sekcji `pipeline` w Taskfile.yml.

## Supported Platforms

| Platform | Command | Output File |
|----------|---------|-------------|
| GitHub Actions | `taskfile ci generate --target github` | `.github/workflows/taskfile.yml` |
| GitLab CI | `taskfile ci generate --target gitlab` | `.gitlab-ci.yml` |
| Gitea Actions | `taskfile ci generate --target gitea` | `.gitea/workflows/taskfile.yml` |
| Drone CI | `taskfile ci generate --target drone` | `.drone.yml` |
| Jenkins | `taskfile ci generate --target jenkins` | `Jenkinsfile` |
| Makefile | `taskfile ci generate --target makefile` | `Makefile` |

## How It Works

```
Taskfile.yml (pipeline section)
        ↓
taskfile ci generate --target github
        ↓
.github/workflows/taskfile.yml (auto-generated)
```

The `pipeline` section in `Taskfile.yml` is the **single source of truth**.
CI generators translate it into platform-specific configs.

## Pipeline Section Anatomy

```yaml
pipeline:
  python_version: "3.12"        # Python version for CI runner
  runner_image: ubuntu-latest    # Default runner image
  install_cmd: pip install taskfile  # How to install taskfile in CI
  branches: [main, develop]     # Trigger branches
  secrets: [GHCR_TOKEN, SSH_PRIVATE_KEY]  # Required secrets
  cache: [~/.cache/pip]         # Global cache paths
  artifacts: [dist/, coverage/] # Global artifact paths

  stages:
    - name: lint
      tasks: [lint]             # Tasks to run in this stage

    - name: test
      tasks: [test]
      artifacts: [coverage/]    # Stage-specific artifacts
      cache: [~/.cache/pip]     # Stage-specific cache

    - name: build
      tasks: [build, push]
      docker_in_docker: true    # Stage needs Docker access

    - name: deploy-staging
      tasks: [deploy-staging]
      env: staging              # Override environment
      when: "branch:develop"    # Auto-trigger on develop

    - name: deploy-prod
      tasks: [deploy-prod]
      env: prod
      when: manual              # Requires manual approval

    - name: release
      tasks: [release]
      when: tag                 # Triggered by git tags (v*)
```

## Stage Triggers (`when`)

| Value | Meaning |
|-------|---------|
| `auto` (default) | Run on every push |
| `manual` | Require manual approval / workflow_dispatch |
| `branch:main` | Only on pushes to `main` branch |
| `branch:develop` | Only on pushes to `develop` branch |
| `tag` | Only on tag pushes (e.g. `v1.0.0`) |

## Usage

```bash
# Generate for a single platform
taskfile ci generate --target github

# Generate for ALL 6 platforms at once
taskfile ci generate --all

# Preview config without writing to disk
taskfile ci preview --target github
taskfile ci preview --target gitlab

# List pipeline stages
taskfile ci list

# Run pipeline locally (same stages as CI)
taskfile ci run
taskfile ci run --stage test          # single stage
taskfile ci run --skip deploy-prod    # skip specific stage
taskfile ci run --stop-at build       # stop after build
```

## Auto-Inference (Alternative)

If you don't want an explicit `pipeline` section, add `stage` fields to tasks:

```yaml
tasks:
  lint:
    stage: lint        # ← auto-inferred as pipeline stage
    cmds: [ruff check src/]
  test:
    stage: test
    cmds: [pytest tests/]
  build:
    stage: build
    cmds: [docker build -t ${IMAGE}:${TAG} .]
```

`taskfile ci generate` will auto-build stages from task `stage` fields.
