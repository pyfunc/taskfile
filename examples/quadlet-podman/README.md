# Quadlet Podman — Compose → Systemd on Low-RAM VPS

Deploy via Podman Quadlet: docker-compose.yml → .container files → systemd na VPS.

## Features covered

- **`service_manager: quadlet`** — deploy strategy uses Quadlet instead of compose
- **`quadlet_dir`** / **`quadlet_remote_dir`** — local + remote paths for .container files
- **`compose`** section — `file`, `override_files`, `network`, `auto_update`
- **`ssh_port: 2222`** — non-standard SSH port
- **`env_file`** — per-environment .env files
- **`silent: true`** — health check suppresses curl command echo
- **`taskfile deploy`** — auto-selects strategy (compose local vs quadlet remote)
- **`taskfile setup`** — one-command VPS provisioning
- **`taskfile quadlet generate/upload`** — Quadlet workflow commands

## Workflow

```
docker-compose.yml
        ↓
taskfile quadlet generate    → deploy/quadlet/*.container
        ↓
taskfile quadlet upload      → scp → ~/.config/containers/systemd/
        ↓
systemctl --user restart     → running as rootless Podman
```

## Usage

```bash
# Local dev
taskfile --env local run dev

# Full prod deploy (build → push → quadlet → restart)
taskfile --env prod run deploy-prod --var TAG=v1.0.0

# Or use built-in deploy command (auto strategy)
taskfile --env prod deploy --var TAG=v1.0.0

# Quadlet workflow step by step
taskfile --env prod run quadlet-generate
taskfile --env prod run quadlet-upload
taskfile --env prod run quadlet-restart

# VPS setup from scratch
taskfile setup 123.45.67.89 --domain app.example.com
# or:
taskfile --env prod run provision

# Monitoring
taskfile --env prod run logs
taskfile --env prod run status
taskfile run health
```

## Why Quadlet?

- **No compose on VPS** — Podman Quadlet uses native systemd
- **Low RAM** — no docker daemon, rootless Podman
- **Auto-update** — `compose.auto_update: true` enables Podman auto-update
- **Reliable** — systemd manages restarts, logging, dependencies
