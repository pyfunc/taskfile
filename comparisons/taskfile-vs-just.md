# Taskfile vs Just

## Quick Comparison

| Feature | Just | Taskfile |
|---------|------|----------|
| Syntax | TOML-like (Justfile) | YAML |
| Task dependencies | ✅ | ✅ |
| Parallel execution | ✅ | ✅ |
| Cross-platform | ✅ | ✅ |
| **Environments** | ❌ | ✅ |
| **SSH remote execution** | ❌ | ✅ (`@remote`) |
| **Fleet management** | ❌ | ✅ (`-G` groups) |
| **Registry authentication** | ❌ | ✅ (`auth setup`) |
| **Quadlet generation** | ❌ | ✅ |
| **VPS setup** | ❌ | ✅ |
| **CI/CD generation** | ❌ | ✅ |

## What is Just?

Just is a command runner written in Rust by Casey Rodarmor. It's designed as a simpler alternative to Make, with a focus on running commands rather than building files.

**Key strengths:**
- Simple, readable syntax
- Great for project-specific recipes
- Cross-platform (Windows, macOS, Linux)
- Built-in help generation

## When to Use Just

- Single-environment projects
- Teams that need simple task running
- No need for remote execution
- No fleet management requirements

## When to Use Taskfile Instead

- Multiple deployment environments (local, staging, prod)
- SSH-based remote execution needed
- Managing fleets of devices (RPi kiosks, edge nodes)
- Registry authentication and publishing
- VPS provisioning
- Podman Quadlet generation

## Side-by-Side Examples

### Basic Task

```toml
# Justfile
deploy:
  echo "Deploying..."
  ./scripts/deploy.sh
```

```yaml
# Taskfile.yml
tasks:
  deploy:
    cmds:
      - echo "Deploying..."
      - ./scripts/deploy.sh
```

### Variables

```toml
# Justfile
image := "myapp"
tag := "latest"

deploy:
  docker build -t {{image}}:{{tag}} .
```

```yaml
# Taskfile.yml
variables:
  IMAGE: myapp
  TAG: latest

tasks:
  deploy:
    cmds:
      - docker build -t ${IMAGE}:${TAG} .
```

### Remote Execution (SSH)

```toml
# Justfile - NO built-in SSH support
deploy-prod:
  ssh deploy@prod.example.com "podman pull myapp:latest"
  ssh deploy@prod.example.com "systemctl restart myapp"
```

```yaml
# Taskfile.yml - Native @remote support
environments:
  prod:
    ssh_host: prod.example.com
    ssh_user: deploy

tasks:
  deploy:
    env: [prod]
    cmds:
      - "@remote podman pull ${IMAGE}:${TAG}"
      - "@remote systemctl --user restart ${APP}"
```

### Fleet Deploy

```toml
# Justfile - Manual SSH for each host
deploy-kiosks:
  ssh pi@kiosk1 "podman pull myapp:v1.0"
  ssh pi@kiosk2 "podman pull myapp:v1.0"
  ssh pi@kiosk3 "podman pull myapp:v1.0"
```

```yaml
# Taskfile.yml - Group with rolling strategy
environments:
  kiosk1: {ssh_host: 192.168.1.10, ssh_user: pi}
  kiosk2: {ssh_host: 192.168.1.11, ssh_user: pi}
  kiosk3: {ssh_host: 192.168.1.12, ssh_user: pi}

environment_groups:
  kiosks:
    members: [kiosk1, kiosk2, kiosk3]
    strategy: rolling
    max_parallel: 2

tasks:
  deploy:
    cmds:
      - "@remote podman pull ${IMAGE}:${TAG}"
```

Usage:
```bash
# Deploy to all kiosks with rolling strategy
taskfile -G kiosks run deploy --var TAG=v1.0
```

## Migration from Just to Taskfile

### Step 1: Convert syntax
- `just` commands → `taskfile run`
- `{{variable}}` → `${VARIABLE}`

### Step 2: Add environments (optional)
Define `environments` section for remote hosts

### Step 3: Use @remote prefix
Replace `ssh user@host "command"` with `"@remote command"`

### Step 4: Add fleet groups (optional)
Define `environment_groups` for batch deploys

## Summary

| Use Case | Recommendation |
|----------|----------------|
| Simple local tasks | Just ✅ |
| Multi-environment deploys | Taskfile ✅ |
| SSH remote execution | Taskfile ✅ |
| Fleet/edge management | Taskfile ✅ |
| Registry publishing | Taskfile ✅ |
| VPS setup | Taskfile ✅ |

## Can They Coexist?

Yes! Use Just for simple local tasks and Taskfile for deployments:

```toml
# Justfile
test:
  cargo test

# Delegate deploy to taskfile
deploy:
  taskfile --env prod run deploy
```

```yaml
# Taskfile.yml
environments:
  prod:
    ssh_host: prod.example.com
    ssh_user: deploy

tasks:
  deploy:
    cmds:
      - "@remote podman pull ${IMAGE}:${TAG}"
      - "@remote systemctl --user restart ${APP}"
```
