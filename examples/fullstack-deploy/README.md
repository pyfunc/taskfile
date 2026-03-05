# Fullstack Deploy — All Built-in Commands Showcase

Kompletny przykład łączący WSZYSTKIE komendy CLI taskfile w jednym projekcie.

## Features covered

- **`taskfile deploy`** — auto-select strategy (compose local / compose remote / quadlet)
- **`taskfile setup`** — one-command VPS provisioning
- **`taskfile release`** — full release orchestration
- **`taskfile init`** — create Taskfile from template
- **`taskfile validate`** — validate config without running
- **`taskfile info`** — detailed task information
- **`taskfile list`** — list tasks + environments
- **`taskfile ci generate/run/preview/list`** — full CI pipeline
- **`--dry-run`** — preview commands without executing
- **`--var KEY=VALUE`** — override variables from CLI
- **`compose`** section — `file`, `override_files`, `network`, `auto_update`
- **`pipeline`** — full CI with `stages`, `when`, `docker_in_docker`, `artifacts`, `cache`, `secrets`
- **3 deploy strategies:** local (compose), staging (remote compose), prod (quadlet)

## Usage — All CLI Commands

```bash
# ─── Project setup ────────────────────────────────────
taskfile init --template full           # create Taskfile.yml
taskfile validate                       # check config
taskfile list                           # show tasks + envs
taskfile info build                     # detailed task info

# ─── Run tasks ────────────────────────────────────────
taskfile run test                       # run a task
taskfile run lint test --var TAG=v1.0   # multiple tasks + var override
taskfile --env prod --dry-run run deploy-prod  # preview without executing

# ─── Deploy (auto strategy) ──────────────────────────
taskfile --env local deploy             # → docker compose up
taskfile --env staging deploy           # → SSH + docker compose
taskfile --env prod deploy              # → quadlet generate + upload + restart

# ─── VPS setup (one command) ─────────────────────────
taskfile setup 123.45.67.89 --domain app.example.com
taskfile setup 123.45.67.89 --ssh-key ~/.ssh/custom --user admin --dry-run

# ─── CI pipeline ─────────────────────────────────────
taskfile ci generate --target github    # generate .github/workflows/
taskfile ci generate --all              # all 6 CI platforms
taskfile ci preview --target gitlab     # preview without writing
taskfile ci list                        # show pipeline stages
taskfile ci run                         # run pipeline locally
taskfile ci run --stage test            # run single stage
taskfile ci run --skip deploy-prod      # skip specific stage

# ─── Release ─────────────────────────────────────────
taskfile release --tag v1.0.0           # full release pipeline
taskfile release --tag v1.0.0 --dry-run # preview release
taskfile release --skip-desktop         # skip desktop builds

# ─── Monitoring ──────────────────────────────────────
taskfile --env staging run logs-staging
taskfile --env prod run logs-prod
taskfile run health
```

## Deploy Strategy Matrix

| Environment | `service_manager` | Strategy | Command |
|-------------|-------------------|----------|---------|
| local | compose | `docker compose up` | `taskfile --env local deploy` |
| staging | compose (remote) | SSH + `docker compose pull/up` | `taskfile --env staging deploy` |
| prod | quadlet | generate → scp → `systemctl restart` | `taskfile --env prod deploy` |
