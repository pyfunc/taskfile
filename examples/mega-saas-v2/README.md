# mega-saas-v2 — Same Power, 80% Less YAML

Side-by-side comparison with `mega-saas/` (the original 987-line example).

## Before vs After

| Metric | mega-saas (v1) | mega-saas-v2 | Reduction |
|--------|---------------|--------------|-----------|
| **Taskfile.yml** | 987 lines | ~310 lines | **-69%** |
| **Extra files** | 4 (2 includes + 2 scripts) | 2 (scripts only) | -50% |
| **Environments** | 60+ lines manual | 15 lines `hosts:` | **-75%** |
| **Build/push/deploy** | 40+ lines manual | 10 lines `deploy:` | **-75%** |
| **DB/monitoring tasks** | 100+ lines in includes | 8 lines `addons:` | **-92%** |
| **Total tasks** | 50+ (all manual) | 50+ (30 generated) | same coverage |

## New Features Used

### `hosts:` — compact environment declaration
```yaml
hosts:
  _defaults: { user: deploy, runtime: podman }
  prod-eu:   { host: eu.example.com, region: eu-west-1 }
  prod-us:   { host: us.example.com, region: us-east-1 }
  _groups:
    all-prod: { members: [prod-eu, prod-us], strategy: canary }
```
Expands to full `environments:` + `environment_groups:` automatically.
Extra keys (like `region`) become uppercase variables (`REGION`).

### `deploy:` — recipe-based deploy pipeline
```yaml
deploy:
  strategy: quadlet
  images:
    api: services/api/Dockerfile
    web: services/web/Dockerfile
  registry: ${REGISTRY}
  health_check: /health
```
Auto-generates: `build-api`, `build-web`, `build-all`, `push-api`, `push-web`, `push-all`, `deploy`, `health`, `rollback`.

### `addons:` — pluggable infrastructure tasks
```yaml
addons:
  - postgres: { db_name: mega_saas }
  - monitoring: { grafana: http://grafana:3000 }
  - redis: { url: redis://redis:6379 }
```
Auto-generates: `db-status`, `db-backup`, `db-migrate`, `db-vacuum`, `mon-status`, `mon-alerts`, `redis-status`, `redis-info`, etc.

### Smart defaults
- `ssh_host` present → `podman` + `quadlet` + `~/.ssh/id_ed25519`
- No `ssh_host` → `docker` + `compose`
- `env_file` defaults to `.env.{env_name}`

### `taskfile explain`
```bash
$ taskfile --env prod-eu explain deploy

📋 deploy (env: prod-eu)
   Deploy via Podman Quadlet (generate → upload → pull → restart)

  Requires:  Docker, SSH to eu.mega-saas.example.com
  Time:      max ~645s with retries
  Retries:   2 (delay: 15s)

  Steps:
    ── dep: build-all ──
    1. 💻 docker build -t ghcr.io/myorg/api:latest ...
    2. 💻 docker build -t ghcr.io/myorg/web:latest ...
    3. 💻 docker build -t ghcr.io/myorg/worker:latest ...
    ── dep: push-all ──
    4. 💻 docker push ghcr.io/myorg/api:latest
    5. 💻 docker push ghcr.io/myorg/web:latest
    6. 💻 docker push ghcr.io/myorg/worker:latest
    7. 💻 taskfile quadlet generate
    8. 💻 taskfile quadlet upload
    9. 🌐 @remote systemctl --user daemon-reload
   10. 🌐 @remote podman pull ghcr.io/myorg/api:latest
   ...

  Variables:
    APP_NAME=mega-saas  DOMAIN=eu.mega-saas.example.com  REGION=eu-west-1  TAG=latest
```

## Structure

```
mega-saas-v2/
├── Taskfile.yml          # ~310 lines (was 987)
├── README.md
└── scripts/
    ├── health.sh         # (reused from v1)
    └── report.py         # (reused from v1)
```
No more `tasks/monitoring.yml` or `tasks/database.yml` — replaced by addons.

## Quick Start

```bash
# Generate this from scratch:
taskfile init --template saas

# Or compare with v1:
diff examples/mega-saas/Taskfile.yml examples/mega-saas-v2/Taskfile.yml
wc -l examples/mega-saas/Taskfile.yml examples/mega-saas-v2/Taskfile.yml
```
