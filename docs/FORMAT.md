# Taskfile.yml Format Reference

Complete reference for Taskfile.yml syntax and structure.

## File Structure

```yaml
version: "1"                    # Required: File format version
name: my-project               # Optional: Project name
description: My description    # Optional: Project description

# Global configuration
variables:                     # Global variables
  KEY: value

environments:                  # Environment definitions
  local:
    # environment config

platforms:                     # Platform definitions
  web:
    # platform config

functions:                     # Reusable functions
  notify:
    # function definition

# Task definitions
tasks:
  task-name:
    # task properties
```

## Top-Level Keys

### version (required)

File format version. Currently "1".

```yaml
version: "1"
```

### name (optional)

Project name for display purposes.

```yaml
name: my-awesome-project
```

### description (optional)

Short project description.

```yaml
description: Deployment automation for microservices
```

### default_env (optional)

Default environment to use when none is specified.

```yaml
default_env: local
```

### default_platform (optional)

Default platform to use when none is specified.

```yaml
default_platform: web
```

### include (optional)

Include external Taskfile.yml files.

```yaml
include:
  - path: ./tasks/build.yml
  - path: ./tasks/deploy.yml
    prefix: deploy
  - ./tasks/test.yml  # String shorthand
```

### compose (optional)

Docker Compose configuration.

```yaml
compose:
  file: docker-compose.yml
  override_files:
    - docker-compose.override.yml
  network: proxy
  auto_update: true
```

### pipeline (optional)

CI/CD pipeline configuration for generation.

```yaml
pipeline:
  python_version: "3.12"
  runner_image: ubuntu-latest
  docker_in_docker: true
  secrets: [GHCR_TOKEN, DEPLOY_KEY]
  cache: [~/.cache/pip, node_modules]
  artifacts: [dist/, coverage/]
  branches: [main]
  
  stages:
    - name: test
      tasks: [lint, test]
      cache: [~/.cache/pip]
      
    - name: build
      tasks: [build, push]
      docker_in_docker: true
```

### environment_defaults (optional)

Default configuration for all environments.

```yaml
environment_defaults:
  ssh_user: deploy
  ssh_key: ~/.ssh/id_ed25519
  container_runtime: podman
```

## Variables Section

Define global variables available to all tasks.

```yaml
variables:
  # Static value
  VERSION: "1.0.0"
  
  # From environment variable
  API_KEY: ${API_KEY}
  
  # With default
  DEBUG: ${DEBUG:-false}
  
  # Complex value
  DOCKER_FLAGS: "--rm -it"
```

Variable substitution:
- `{{VAR}}` — Jinja2 style
- `${VAR}` — Shell style
- `$VAR` — Simple style

## Environments Section

Define deployment environments.

```yaml
environments:
  local:
    container_runtime: docker
    compose_command: docker compose
    env_file: .env.local
  
  staging:
    ssh_host: ${STAGING_HOST}
    ssh_user: deploy
    ssh_key: ~/.ssh/id_ed25519
    container_runtime: podman
    env_file: .env.staging
  
  prod:
    ssh_host: ${PROD_HOST}
    ssh_user: deploy
    ssh_key: ~/.ssh/id_ed25519
    container_runtime: podman
    service_manager: quadlet
    env_file: .env.prod
```

### Environment Properties

| Property | Type | Description |
|----------|------|-------------|
| `container_runtime` | string | docker, podman |
| `compose_command` | string | docker compose, podman-compose |
| `ssh_host` | string | Remote host address |
| `ssh_user` | string | SSH username |
| `ssh_key` | string | Path to SSH key |
| `ssh_port` | string | SSH port (default: 22) |
| `env_file` | string | Environment file path |
| `service_manager` | string | systemd, quadlet, compose |
| `compose_file` | string | Docker Compose file path |
| `quadlet_dir` | string | Local quadlet directory |
| `quadlet_remote_dir` | string | Remote quadlet directory |
| `variables` | object | Environment-specific variables |

## Platforms Section

Define target platforms.

```yaml
platforms:
  web:
    envs: [staging, prod]
    variables:
      DOMAIN: example.com
  
  desktop:
    envs: [local]
    variables:
      TARGET: electron
```

## Functions Section

Define reusable functions.

```yaml
functions:
  notify:
    lang: python
    code: |
      import os
      message = os.environ.get('FN_ARGS', 'Done')
      print(f"[NOTIFY] {message}")
  
  health-check:
    lang: shell
    file: ./scripts/health.sh
  
  deploy-script:
    lang: node
    code: |
      console.log("Deploying...")
```

### Function Languages

- `shell` (default) — Bash/sh commands
- `python` — Python code
- `node` — Node.js/JavaScript
- `binary` — External executable

## Tasks Section

Task definitions.

```yaml
tasks:
  build:
    desc: Build the application
    deps: [lint]
    cmds:
      - docker build -t myapp .
```

### Task Properties

#### desc (optional)

Task description for documentation.

```yaml
desc: Build Docker image and push to registry
```

#### cmds (required)

List of commands to execute.

```yaml
cmds:
  - echo "Starting..."
  - docker build -t myapp .
  - docker push myapp
```

#### deps (optional)

Dependencies that run first.

```yaml
deps:
  - lint
  - test
```

With parallel execution:
```yaml
deps: [lint, test, build]
parallel: true
```

#### env (optional)

Restrict to specific environments.

```yaml
env: [staging, prod]
```

#### platform (optional)

Restrict to specific platforms.

```yaml
platform: [web]
```

#### condition (optional)

Skip task if condition is false.

```yaml
condition: "${DEPLOY_ENABLED} == true"
```

#### parallel (optional)

Run dependencies in parallel. Default: false.

```yaml
parallel: true
```

#### ignore_errors (optional)

Continue on command failure. Default: false.

```yaml
ignore_errors: true
```

#### continue_on_error (optional)

Continue on command failure. Default: false. Alias for `ignore_errors`.

```yaml
continue_on_error: true
```

#### retries (optional)

Number of retry attempts. Default: 0.

```yaml
retries: 3
```

#### retry_delay (optional)

Seconds between retries. Default: 5.

```yaml
retry_delay: 10
```

#### timeout (optional)

Maximum execution time in seconds. Default: 0 (no timeout).

```yaml
timeout: 300  # 5 minutes
```

#### tags (optional)

Tags for selective execution.

```yaml
tags: [ci, deploy]
```

Run with tags:
```bash
taskfile run --tags ci test
```

#### silent (optional)

Suppress command output. Default: false.

```yaml
silent: true
```

#### register (optional)

Capture command output to variable.

```yaml
cmds:
  - cat version.txt
register: VERSION
```

Use later:
```yaml
cmds:
  - echo "Version is {{VERSION}}"
```

#### stage (optional)

Assign task to a CI/CD stage.

```yaml
stage: build
```

#### dir (optional)

Working directory for commands. Alias for `working_dir`.

```yaml
dir: ./subdir
```

#### working_dir (optional)

Working directory for commands.

```yaml
working_dir: ./subdir
```

## Environment Defaults

Define default configuration for all environments.

```yaml
environment_defaults:
  ssh_user: deploy
  ssh_key: ~/.ssh/id_ed25519
  container_runtime: podman
  ssh_port: 2222
```

## Environment Groups

Define groups of environments for fleet deployment.

```yaml
environment_groups:
  all-servers:
    strategy: rolling  # rolling, canary, parallel
    members:
      - server-01
      - server-02
      - server-03
  
  kiosks:
    strategy: parallel
    max_parallel: 5
    members: [kiosk-01, kiosk-02, ...]
```

Strategies:
- `rolling` — One at a time, pause between
- `canary` — First N, confirm, then rest
- `parallel` — All at once (respect max_parallel)

### Group Properties

| Property | Type | Description |
|----------|------|-------------|
| `strategy` | string | rolling, canary, parallel |
| `members` | list | Environment names in the group |
| `max_parallel` | integer | Max concurrent deployments (rolling/parallel) |
| `canary_count` | integer | Number of canary deployments (canary) |

## Special Command Prefixes

### @fn — Call Embedded Function

```yaml
cmds:
  - "@fn notify Deployment complete"
```

### @python — Inline Python

```yaml
cmds:
  - "@python print('Hello from Python')"
  - "@python import os; print(os.environ['ENV'])"
```

### @remote — SSH Execution

```yaml
cmds:
  - "@remote docker ps"
  - "@remote systemctl status myapp"
```

## Complete Example

```yaml
version: "1"
name: saas-platform
description: Multi-tenant SaaS deployment

variables:
  VERSION: ${VERSION:-1.0.0}
  IMAGE: ghcr.io/myorg/myapp
  DOMAIN: ${DOMAIN:-localhost}

environments:
  local:
    container_runtime: docker
    compose_command: docker compose
    env_file: .env.local
  
  staging:
    ssh_host: ${STAGING_HOST}
    ssh_user: deploy
    container_runtime: podman
    env_file: .env.staging
  
  prod:
    ssh_host: ${PROD_HOST}
    ssh_user: deploy
    container_runtime: podman
    service_manager: quadlet
    env_file: .env.prod

platforms:
  web:
    envs: [local, staging, prod]
  
  api:
    envs: [local, staging, prod]

functions:
  notify:
    lang: python
    code: |
      import os
      msg = os.environ.get('FN_ARGS', 'Done')
      print(f"[NOTIFY] {msg}")
  
  health-check:
    lang: shell
    code: |
      curl -sf http://localhost:8000/health || exit 1

environment_groups:
  all-prod:
    strategy: rolling
    members: [web-01, web-02, api-01, api-02]

tasks:
  lint:
    desc: Run linters
    tags: [ci, quality]
    cmds:
      - flake8 src/
      - black --check src/
  
  test:
    desc: Run tests
    tags: [ci, quality]
    deps: [lint]
    cmds:
      - pytest --cov=src
  
  build:
    desc: Build application image
    tags: [ci, deploy]
    deps: [test]
    cmds:
      - docker build -t ${IMAGE}:${VERSION} .
      - docker tag ${IMAGE}:${VERSION} ${IMAGE}:latest
  
  push:
    desc: Push image to registry
    tags: [deploy]
    deps: [build]
    env: [staging, prod]
    cmds:
      - docker push ${IMAGE}:${VERSION}
      - docker push ${IMAGE}:latest
  
  deploy:
    desc: Deploy to environment
    tags: [deploy]
    deps: [push]
    env: [staging, prod]
    retries: 2
    retry_delay: 10
    cmds:
      - "@fn notify Starting deployment to {{ENV}}"
      - "@remote podman pull ${IMAGE}:${VERSION}"
      - "@remote systemctl --user restart myapp"
      - sleep 5
      - "@fn health-check"
      - "@fn notify Deployment complete"
  
  release:
    desc: Full release pipeline
    deps: [lint, test, build, push, deploy]
    parallel: false
  
  clean:
    desc: Clean up
    ignore_errors: true
    cmds:
      - docker system prune -f
      - docker volume prune -f
```

---

Last updated: 2026-03-05
