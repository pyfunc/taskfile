# Taskfile vs Make

## Quick Comparison

| Feature | Make | Taskfile |
|---------|------|----------|
| File-based dependencies | ✅ | ❌ |
| Task orchestration | ✅ | ✅ |
| Cross-compilation | ✅ | ❌ |
| **YAML syntax** | ❌ | ✅ |
| **Environments** | ❌ | ✅ |
| **`@local`/`@remote` execution** | ❌ | ✅ |
| **Fleet management** | ❌ | ✅ |
| **Registry authentication** | ❌ | ✅ |
| **Quadlet generation** | ❌ | ✅ |
| **VPS setup** | ❌ | ✅ |
| **CI/CD generation** | ❌ | ✅ |

## What is Make?

Make is a build automation tool originally created for C/C++ compilation. It uses file timestamps to determine what needs rebuilding.

**Key strengths:**
- Universal availability (pre-installed on most Unix systems)
- File-based dependency tracking
- Incremental builds
- Mature, stable
- Fast for compilation tasks

## When to Use Make

- C/C++ projects with file dependencies
- Compilation with incremental builds
- File-based dependency graphs
- Systems programming
- Teams already familiar with Make

## When to Use Taskfile Instead

- Multi-environment deployments
- SSH-based remote execution
- Fleet management (RPi kiosks, edge devices)
- YAML preference over Makefile syntax
- Registry authentication and publishing
- Podman Quadlet generation
- VPS provisioning
- CI/CD config generation

## Side-by-Side Examples

### Basic Task

```makefile
# Makefile
.PHONY: build test

build:
	go build -o myapp .

test:
	go test ./...
```

```yaml
# Taskfile.yml
tasks:
  build:
    cmds:
      - go build -o myapp .
  
  test:
    cmds:
      - go test ./...
```

### Variables

```makefile
# Makefile
IMAGE := myapp
TAG := latest

build:
	docker build -t $(IMAGE):$(TAG) .
```

```yaml
# Taskfile.yml
variables:
  IMAGE: myapp
  TAG: latest

tasks:
  build:
    cmds:
      - docker build -t ${IMAGE}:${TAG} .
```

### File Dependencies (Make's strength)

```makefile
# Makefile - Rebuilds only when source changes
app: main.go utils.go
	go build -o app .

clean:
	rm -f app
```

```yaml
# Taskfile.yml - No file dependency tracking
tasks:
  build:
    cmds:
      - go build -o app .
  
  clean:
    cmds:
      - rm -f app
```

Make wins for file-based incremental builds.

### Remote Execution (SSH)

```makefile
# Makefile - Manual SSH
deploy-prod:
	ssh deploy@prod.example.com "podman pull myapp:latest"
	ssh deploy@prod.example.com "systemctl restart myapp"

deploy-kiosks:
	ssh pi@kiosk1 "podman pull myapp:v1.0"
	ssh pi@kiosk2 "podman pull myapp:v1.0"
	ssh pi@kiosk3 "podman pull myapp:v1.0"
```

```yaml
# Taskfile.yml - Native @remote and groups
environments:
  kiosk1: {ssh_host: 192.168.1.10, ssh_user: pi}
  kiosk2: {ssh_host: 192.168.1.11, ssh_user: pi}
  kiosk3: {ssh_host: 192.168.1.12, ssh_user: pi}
  prod: {ssh_host: prod.example.com, ssh_user: deploy}

environment_groups:
  kiosks:
    members: [kiosk1, kiosk2, kiosk3]
    strategy: rolling
    max_parallel: 2

tasks:
  deploy:
    env: [prod]
    cmds:
      - "@remote podman pull ${IMAGE}:${TAG}"
      - "@remote systemctl --user restart ${APP}"
```

Usage:
```bash
# Deploy to all kiosks with rolling strategy
taskfile -G kiosks run deploy --var TAG=v1.0
```

### Multi-Environment Deploy

```makefile
# Makefile - Repetitive targets
deploy-local:
	docker compose up -d

deploy-staging:
	ssh deploy@staging "docker compose up -d"

deploy-prod:
	ssh deploy@prod.example.com "podman pull ${IMAGE}:${TAG}"
	ssh deploy@prod.example.com "systemctl --user restart ${APP}"
```

```yaml
# Taskfile.yml - One task, all environments
environments:
  local:
    container_runtime: docker
    compose_command: docker compose
  
  staging:
    ssh_host: staging.example.com
    ssh_user: deploy
    container_runtime: docker
  
  prod:
    ssh_host: prod.example.com
    ssh_user: deploy
    container_runtime: podman
    service_manager: quadlet

tasks:
  deploy:
    env: [local, staging, prod]
    cmds:
      - "@local ${COMPOSE} up -d"
      - "@remote podman pull ${IMAGE}:${TAG}"
      - "@remote systemctl --user restart ${APP}"
```

Usage:
```bash
taskfile --env local run deploy
taskfile --env staging run deploy
taskfile --env prod run deploy
```

## Migration from Make to Taskfile

### Step 1: Convert syntax

| Make | Taskfile |
|------|----------|
| `target:` | `tasks:` with `name:` |
| `$(VAR)` | `${VAR}` |
| `.PHONY:` | Not needed |
| `\t` (tab) | YAML indentation |

### Step 2: Add environments (optional)

Replace separate Make targets with environment abstraction.

### Step 3: Use @remote prefix

Replace `ssh user@host "command"` with `"@remote command"`.

### Step 4: Add fleet groups (optional)

Define `environment_groups` for batch deploys.

## Recommended Combo: Make + Taskfile

Use both tools for their strengths:

```makefile
# Makefile - C/C++ compilation with file deps
app: main.o utils.o
	gcc -o app main.o utils.o

main.o: main.c
	gcc -c main.c

utils.o: utils.c
	gcc -c utils.c

# Delegate deployment to taskfile
deploy:
	taskfile --env prod run deploy

test:
	taskfile run test

.PHONY: deploy test
```

```yaml
# Taskfile.yml - Deployments and fleet management
environments:
  prod:
    ssh_host: prod.example.com
    ssh_user: deploy

environment_groups:
  kiosks:
    members: [kiosk1, kiosk2, kiosk3]
    strategy: rolling

tasks:
  deploy:
    cmds:
      - "@remote podman pull ${IMAGE}:${TAG}"
      - "@remote systemctl --user restart ${APP}"
  
  test:
    cmds:
      - ./run-tests.sh
```

## Summary

| Use Case | Recommendation |
|----------|----------------|
| C/C++ compilation | Make ✅ |
| File-based incremental builds | Make ✅ |
| Simple local tasks | Make ✅ |
| Multi-environment deploys | Taskfile ✅ |
| SSH remote execution | Taskfile ✅ |
| Fleet/edge management | Taskfile ✅ |
| YAML preference | Taskfile ✅ |
| Registry publishing | Taskfile ✅ |
| VPS setup | Taskfile ✅ |

## Key Differences

### Make's Advantages
1. **File dependencies** - Only rebuilds changed files
2. **Speed** - Extremely fast for compilation
3. **Ubiquity** - Available everywhere
4. **Maturity** - 40+ years of stability

### Taskfile's Advantages
1. **YAML syntax** - More readable, easier to parse
2. **Environments** - Abstract deployment targets
3. **SSH execution** - Native `@remote` support
4. **Fleet management** - Groups, rolling deploys
5. **Registry auth** - Interactive token setup
6. **Quadlet gen** - docker-compose → systemd
7. **VPS setup** - One-command provisioning
8. **CI/CD gen** - GitHub Actions, GitLab CI templates

## Verdict

Don't choose one or the other — **use both**:

- **Make** for compilation and file-based workflows
- **Taskfile** for deployment, fleet management, and infrastructure

They're complementary tools that excel in different domains.
