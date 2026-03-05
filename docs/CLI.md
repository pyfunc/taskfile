# Taskfile CLI Reference

Complete reference for all `taskfile` commands, flags, and options.

## Global Options

These options apply to all commands and must be placed **before** the subcommand:

```bash
taskfile [GLOBAL OPTIONS] <command> [COMMAND OPTIONS]
```

| Flag | Short | Description | Default |
|------|-------|-------------|---------|
| `--file PATH` | `-f` | Path to Taskfile.yml | auto-detect |
| `--env NAME` | `-e` | Target environment | `local` |
| `--env-group NAME` | `-G` | Target environment group (fleet) | — |
| `--platform NAME` | `-p` | Target platform (e.g. desktop, web) | — |
| `--var KEY=VALUE` | | Override variable (repeatable) | — |
| `--dry-run` | | Show commands without executing | `false` |
| `--verbose` | `-v` | Verbose output | `false` |
| `--version` | | Show version and exit | — |
| `--help` | | Show help and exit | — |

---

## Commands

### `taskfile run`

Run one or more tasks.

```bash
taskfile run <task> [task2 ...] [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--tags TAGS` | Run only tasks matching comma-separated tags |

**Examples:**
```bash
taskfile run build
taskfile run build deploy --env prod
taskfile run release --var TAG=v1.2.3
taskfile run deploy --env prod --dry-run
taskfile -G kiosks run deploy-kiosk --var TAG=v1.0
taskfile run --tags ci build test lint
```

---

### `taskfile list`

List available tasks and environments.

```bash
taskfile list
taskfile --env prod list
```

---

### `taskfile validate`

Validate the Taskfile without running anything. Reports warnings for missing dependencies, unknown environments, and empty tasks.

```bash
taskfile validate
taskfile -f path/to/Taskfile.yml validate
```

---

### `taskfile init`

Interactive project initialization wizard. Creates a `Taskfile.yml` with environments, tasks, and optional CI/CD pipeline.

```bash
taskfile init
```

---

### `taskfile doctor`

Run project diagnostics — checks Taskfile validity, environment files, Docker/Podman availability, SSH connectivity, and port conflicts.

```bash
taskfile doctor
```

---

### `taskfile info`

Show detailed information about the current Taskfile configuration (environments, variables, tasks, pipeline).

```bash
taskfile info
```

---

### `taskfile deploy`

Full deploy pipeline: build → push → generate Quadlet → upload → restart. Automatically selects the correct strategy based on the target environment's `service_manager`.

```bash
taskfile --env local deploy          # docker compose up -d
taskfile --env prod deploy           # quadlet or compose on remote
taskfile --env prod deploy --var TAG=v1.2.3
```

| Option | Description |
|--------|-------------|
| `--compose PATH` | Override path to docker-compose.yml |

**Deploy strategies (auto-selected by `service_manager`):**
- **local** → `docker compose up -d`
- **compose** → SSH + `docker compose pull/up` on remote
- **quadlet** → generate `.container` files → scp → `systemctl restart`

---

### `taskfile setup`

One-command VPS provisioning: SSH key copy → system packages → Podman → firewall → deploy user → first deploy.

```bash
taskfile setup 123.45.67.89 --domain app.example.com
taskfile setup --user deploy --ssh-key ~/.ssh/id_ed25519
```

| Option | Description | Default |
|--------|-------------|---------|
| `IP` | Server IP address (or interactive) | — |
| `--ssh-key PATH` | SSH private key path | `~/.ssh/id_ed25519` |
| `--user NAME` | Deploy user name | `deploy` |
| `--domain NAME` | Domain name | IP address |
| `--ports LIST` | Comma-separated ports to open | `22,80,443` |
| `--dry-run` | Show commands only | `false` |
| `--skip-provision` | Skip VPS provisioning | `false` |
| `--skip-deploy` | Skip application deploy | `false` |

---

### `taskfile health`

Run health checks against the current environment.

```bash
taskfile --env prod health
```

---

### `taskfile watch`

Watch files for changes and re-run tasks automatically.

```bash
taskfile watch build test
taskfile watch build --path src/ --debounce 500
```

| Option | Description | Default |
|--------|-------------|---------|
| `--path PATH` | Directory to watch | `.` |
| `--debounce MS` | Debounce interval in ms | `300` |

---

### `taskfile graph`

Visualize task dependency graph.

```bash
taskfile graph
taskfile graph build --dot           # Output DOT format
taskfile graph --output graph.png    # Save to file
```

| Option | Description |
|--------|-------------|
| `TASK` | Show graph for specific task |
| `--dot` | Output in DOT format |
| `--output PATH` | Save graph to file |

---

### `taskfile serve`

Start web dashboard for managing tasks in a browser.

```bash
taskfile serve                   # Default port 8080
taskfile serve -p 3000           # Custom port
taskfile serve --no-browser      # Don't auto-open browser
```

| Option | Description | Default |
|--------|-------------|---------|
| `--port` / `-p` | Server port | `8080` |
| `--no-browser` | Don't auto-open browser | `false` |

---

### `taskfile release`

Create a tagged release — build, push, deploy with version tag.

```bash
taskfile release --tag v1.2.3
taskfile release --tag v1.2.3 --dry-run
```

| Option | Description |
|--------|-------------|
| `--tag VERSION` | Release version tag |
| `--skip-desktop` | Skip desktop builds |
| `--skip-landing` | Skip landing page |
| `--skip-health` | Skip health checks |
| `--dry-run` | Show commands only |
| `--force` | Force release |

---

### `taskfile rollback`

Rollback to a previous release tag.

```bash
taskfile rollback v1.1.0
taskfile rollback v1.1.0 --domain app.example.com
```

| Option | Description |
|--------|-------------|
| `TARGET_TAG` | Tag to rollback to |
| `--domain NAME` | Domain name |
| `--dry-run` | Show commands only |

---

### `taskfile import`

Import CI/CD config, Makefile, or script INTO Taskfile.yml.

```bash
taskfile import .github/workflows/ci.yml
taskfile import .gitlab-ci.yml --type gitlab-ci
taskfile import Makefile -o Taskfile.yml
taskfile import deploy.sh --type shell
```

| Option | Description | Default |
|--------|-------------|---------|
| `SOURCE` | Source file path | (required) |
| `--type TYPE` | Source type (auto-detected) | auto |
| `-o` / `--output` | Output path | `Taskfile.yml` |
| `--force` | Overwrite existing | `false` |

**Supported source types:** `github-actions`, `gitlab-ci`, `makefile`, `shell`, `dockerfile`

---

### `taskfile export`

Export Taskfile.yml to CI/CD config or other formats.

```bash
taskfile export --type github
taskfile export --type gitlab -o .gitlab-ci.yml
```

| Option | Description | Default |
|--------|-------------|---------|
| `--type TYPE` | Target format | (required) |
| `-o` / `--output` | Output path | auto |
| `--workflow-name` | CI workflow name | — |
| `--project-name` | Project name override | — |

---

### `taskfile detect`

Detect existing CI/CD configs and build tools in the project.

```bash
taskfile detect
```

---

## Command Groups

### `taskfile ci`

Generate CI/CD configs and run pipelines locally.

#### `taskfile ci generate`

```bash
taskfile ci generate --target github
taskfile ci generate --target github --target gitlab
taskfile ci generate --all
taskfile ci generate --target makefile
```

| Option | Description |
|--------|-------------|
| `--target PLATFORM` | CI platform (repeatable) |
| `--all` | Generate for all platforms |
| `-o` / `--output` | Output directory |

**Supported targets:** `github`, `gitlab`, `gitea`, `drone`, `jenkins`, `makefile`

#### `taskfile ci run`

Run the CI/CD pipeline locally.

```bash
taskfile ci run
```

#### `taskfile ci preview`

Preview generated CI config without writing files.

```bash
taskfile ci preview --target gitlab
```

---

### `taskfile fleet`

Manage a fleet of devices (RPi, edge nodes, kiosks).

#### `taskfile fleet status`

```bash
taskfile fleet status
taskfile fleet status --group kiosks
```

| Option | Description |
|--------|-------------|
| `--group NAME` | Only show devices in this group |

#### `taskfile fleet repair`

```bash
taskfile fleet repair kiosk-lobby
taskfile fleet repair kiosk-lobby --auto-fix
```

| Option | Description |
|--------|-------------|
| `ENV_NAME` | Environment name to repair |
| `--auto-fix` | Apply fixes automatically |

#### `taskfile fleet list`

```bash
taskfile fleet list
```

---

### `taskfile auth`

Manage registry authentication tokens.

#### `taskfile auth setup`

Interactive registry authentication setup.

```bash
taskfile auth setup
taskfile auth setup --registry ghcr.io
```

| Option | Description |
|--------|-------------|
| `--registry URL` | Registry URL |

#### `taskfile auth verify`

Verify saved authentication tokens.

```bash
taskfile auth verify
```

---

### `taskfile quadlet`

Generate and manage Podman Quadlet files.

#### `taskfile quadlet generate`

```bash
taskfile quadlet generate
taskfile quadlet generate --env-file .env.prod
```

#### `taskfile quadlet upload`

```bash
taskfile quadlet upload --env prod
```

---

### `taskfile version`

Manage project versioning.

#### `taskfile version show`

```bash
taskfile version show
```

#### `taskfile version bump`

```bash
taskfile version bump patch
taskfile version bump minor --dry-run
taskfile version bump major --force
```

| Option | Description |
|--------|-------------|
| `PART` | Version part: `major`, `minor`, `patch` |
| `--dry-run` | Show without applying |
| `--force` | Skip confirmation |

#### `taskfile version set`

```bash
taskfile version set 2.0.0
taskfile version set 2.0.0 --dry-run
```

---

### `taskfile docker`

Docker management utilities.

#### `taskfile docker ps`

Show running Docker containers.

```bash
taskfile docker ps
```

#### `taskfile docker stop-port`

Stop containers using a specific port.

```bash
taskfile docker stop-port 8080
taskfile docker stop-port 3000 -y
```

#### `taskfile docker stop-all`

Stop all running Docker containers.

```bash
taskfile docker stop-all
taskfile docker stop-all -y
```

#### `taskfile docker compose-down`

Run `docker compose down` in a directory.

```bash
taskfile docker compose-down
taskfile docker compose-down --dir ./services
```

---

### `taskfile cache`

Manage task result cache.

#### `taskfile cache show`

```bash
taskfile cache show
```

#### `taskfile cache clear`

```bash
taskfile cache clear                  # Clear all
taskfile cache clear --task build     # Clear specific task
```

| Option | Description |
|--------|-------------|
| `--task NAME` | Clear cache for specific task |
| `--all` | Clear all cached results |

---

### `taskfile pkg`

Package registry — search, install, and manage shared Taskfile packages.

#### `taskfile pkg search`

```bash
taskfile pkg search deploy
taskfile pkg search docker --limit 10
```

#### `taskfile pkg install`

```bash
taskfile pkg install deploy-utils
taskfile pkg install deploy-utils@1.0.0
```

#### `taskfile pkg list`

```bash
taskfile pkg list
taskfile pkg list --all
```

#### `taskfile pkg uninstall`

```bash
taskfile pkg uninstall deploy-utils
```

#### `taskfile pkg info`

```bash
taskfile pkg info deploy-utils
```

---

## Command Prefixes in Tasks

Commands inside task `cmds` support special prefixes:

| Prefix | Description | Example |
|--------|-------------|---------|
| `@local` | Run only on local environments (no SSH) | `@local ${COMPOSE} logs -f` |
| `@remote` | Run only on remote environments (via SSH) | `@remote podman ps` |
| `@fn` | Call embedded function | `@fn notify-slack` |
| `@python` | Execute inline Python code | `@python print("hello")` |

**`@local`/`@remote` routing:** When a task has `env: [local, prod]`, commands prefixed with `@local` execute only when `--env local`, and `@remote` commands execute only when `--env prod` (or any env with `ssh_host`).

---

## Built-in Variables

| Variable | Source | Description |
|----------|--------|-------------|
| `${COMPOSE}` | auto | Expands to `compose_command [--env-file env_file]` from environment |
| `${APP_NAME}` | `name` field | Project name |
| `${TAG}` | `variables` | Image/release tag |
| `${REGISTRY}` | `variables` | Container registry URL |
| `${SSH_HOST}` | environment | SSH hostname |
| `${SSH_USER}` | environment | SSH username |
| Any custom | `variables` / `--var` | User-defined variables |

---

## Environment Variables

| Env Var | Description |
|---------|-------------|
| `TASKFILE_PATH` | Override Taskfile search path |
| `TASKFILE_ENV` | Default environment name |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Task failure, parse error, or unknown task |

---

## Shell Completion

Generate completion scripts for your shell:

```bash
# Bash
eval "$(taskfile completion bash)"

# Zsh
eval "$(taskfile completion zsh)"

# Fish
taskfile completion fish | source
```
