# Taskfile vs Task (go-task.dev)

## Quick Comparison

| Feature | Task (go-task) | Taskfile |
|---------|---------------|----------|
| YAML config | ✅ Taskfile.yml | ✅ Taskfile.yml |
| Task dependencies | ✅ | ✅ |
| Variables | ✅ | ✅ |
| Cross-platform | ✅ | ✅ |
| **Environments** | ❌ | ✅ |
| **Environment groups** | ❌ | ✅ |
| **SSH remote execution** | ❌ | ✅ (`@remote`) |
| **Fleet management** | ❌ | ✅ (`fleet status`, `fleet repair`) |
| **Multi-registry publish** | ❌ | ✅ |
| **Quadlet generation** | ❌ | ✅ |
| **VPS setup** | ❌ | ✅ |
| **Registry authentication** | ❌ | ✅ (interactive) |
| **CI/CD config generation** | ❌ | ✅ |

## What is Task (go-task.dev)?

Task is a task runner/build tool written in Go. It aims to be simpler and easier to use than GNU Make.

**Key strengths:**
- Fast (compiled Go binary)
- Wide platform support
- Mature ecosystem
- Good documentation
- Taskfile.yml format (similar to taskfile)

## When to Use Task (go-task)

- Simple task orchestration
- No multi-environment requirements
- No SSH execution needed
- Speed is critical
- Go-centric ecosystem

## When to Use Taskfile Instead

- Multiple deployment environments needed
- SSH-based remote execution (`@remote`)
- Fleet management (groups of devices)
- Podman Quadlet generation
- Registry authentication setup
- VPS one-command provisioning
- CI/CD config generation

## Side-by-Side Examples

### Basic Task

```yaml
# Taskfile.yml (go-task)
version: '3'

tasks:
  build:
    cmds:
      - go build -o myapp .
    
  test:
    cmds:
      - go test ./...
```

```yaml
# Taskfile.yml (taskfile)
version: "1"

tasks:
  build:
    cmds:
      - go build -o myapp .
    
  test:
    cmds:
      - go test ./...
```

### Variables

```yaml
# Taskfile.yml (go-task)
version: '3'

vars:
  IMAGE: myapp
  TAG: latest

tasks:
  build:
    cmds:
      - docker build -t {{.IMAGE}}:{{.TAG}} .
```

```yaml
# Taskfile.yml (taskfile)
version: "1"

variables:
  IMAGE: myapp
  TAG: latest

tasks:
  build:
    cmds:
      - docker build -t ${IMAGE}:${TAG} .
```

### Remote Execution (SSH)

```yaml
# Taskfile.yml (go-task) - NO native SSH
version: '3'

tasks:
  deploy-prod:
    cmds:
      - ssh deploy@prod.example.com "podman pull myapp:latest"
      - ssh deploy@prod.example.com "systemctl restart myapp"
```

```yaml
# Taskfile.yml (taskfile) - Native @remote
version: "1"

environments:
  prod:
    ssh_host: prod.example.com
    ssh_user: deploy
    ssh_key: ~/.ssh/id_ed25519

tasks:
  deploy:
    env: [prod]
    cmds:
      - "@remote podman pull ${IMAGE}:${TAG}"
      - "@remote systemctl --user restart ${APP}"
```

### Fleet Deploy

```yaml
# Taskfile.yml (go-task) - Manual approach
version: '3'

tasks:
  deploy-kiosk1:
    cmds:
      - ssh pi@192.168.1.10 "podman pull myapp:v1.0"
  
  deploy-kiosk2:
    cmds:
      - ssh pi@192.168.1.11 "podman pull myapp:v1.0"
  
  deploy-all:
    deps: [deploy-kiosk1, deploy-kiosk2]
```

```yaml
# Taskfile.yml (taskfile) - Environment groups
version: "1"

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
      - "@remote systemctl --user restart ${APP}"
```

Usage:
```bash
# Deploy to all kiosks with rolling strategy
taskfile -G kiosks run deploy --var TAG=v1.0

# Check fleet status
taskfile fleet status --group kiosks

# Repair a device
taskfile fleet repair kiosk1
```

## Unique Taskfile Features

### Environment Groups with Strategies

```yaml
environment_groups:
  production:
    members: [server1, server2, server3, server4]
    strategy: canary    # rolling | canary | parallel
    canary_count: 1
```

### Fleet Commands

```bash
# Status check on all remote environments
taskfile fleet status

# List all environments and groups
taskfile fleet list

# Auto-repair diagnostics
taskfile fleet repair kiosk1 --auto-fix
```

### Registry Authentication

```bash
# Interactive setup
taskfile auth setup

# Verify tokens
taskfile auth verify
```

### Quadlet Generation

```bash
# Generate Podman Quadlet from docker-compose.yml
taskfile quadlet generate --env-file .env.prod
```

### VPS Setup

```bash
# One-command VPS provisioning
taskfile setup 123.45.67.89 --domain app.example.com
```

## Migration from Task (go-task) to Taskfile

### 1. File Names
Both use `Taskfile.yml`, but they can coexist:
- `Taskfile.yml` — taskfile (primary)
- `Taskfile.dist.yml` — go-task (legacy)

### 2. Syntax Changes

| go-task | taskfile |
|-----------|----------|
| `version: '3'` | `version: "1"` |
| `vars:` | `variables:` |
| `{{.VAR}}` | `${VAR}` |
| `deps:` | `deps:` (same) |

### 3. Add Environments (new)

```yaml
environments:
  local:
    container_runtime: docker
  prod:
    ssh_host: prod.example.com
    ssh_user: deploy
```

### 4. Use @remote prefix

Replace manual SSH commands with `@remote` prefixed commands.

## Can They Coexist?

Yes! Since both use similar filenames, you have options:

**Option 1: Separate directories**
```
project/
├── Taskfile.yml          # taskfile (deployments)
├── scripts/
│   └── Taskfile.yml      # go-task (build scripts)
```

**Option 2: Different filenames**
```
project/
├── Taskfile.yml          # taskfile
├── Taskfile.dist.yml     # go-task
```

**Option 3: Taskfile calls go-task**
```yaml
# Taskfile.yml (taskfile)
tasks:
  build:
    cmds:
      - task -f scripts/Taskfile.yml build
  
  deploy:
    deps: [build]
    cmds:
      - "@remote podman pull ${IMAGE}:${TAG}"
```

## Summary

| Use Case | Recommendation |
|----------|----------------|
| Simple task orchestration | Task (go-task) ✅ |
| Speed-critical builds | Task (go-task) ✅ |
| Multi-environment deploys | Taskfile ✅ |
| SSH remote execution | Taskfile ✅ |
| Fleet/edge management | Taskfile ✅ |
| Podman Quadlet | Taskfile ✅ |
| VPS provisioning | Taskfile ✅ |
| Registry publishing | Taskfile ✅ |

## Verdict

Both tools are excellent. Choose **Task (go-task)** for simpler projects and **Taskfile** when you need:
- Environment management
- Remote SSH execution
- Fleet operations
- Registry integration
- Infrastructure automation
