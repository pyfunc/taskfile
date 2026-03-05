# codereview.pl - Complete Real-World Example

Pełny projekt produkcyjny z docker-compose.yml jako single source of truth.

## Co zawiera ten przykład?

✅ **docker-compose.yml** - jeden plik dla wszystkich środowisk  
✅ **20+ tasków** - kompletny workflow  
✅ **4 etapy pipeline** - test, build, generate, deploy  
✅ **6 platform CI/CD** - GitHub, GitLab, Gitea, Drone, Jenkins, Makefile  
✅ **Quadlet** - auto-generowanie z docker-compose  

## Architektura

```
docker-compose.yml
├── .env.local    → docker compose up (local)
├── .env.prod     → podman quadlet (prod)
└── deploy/
    └── quadlet/  → auto-generowane .container
```

## Struktura projektu

```
codereview.pl/
├── docker-compose.yml      # Single source of truth
├── Taskfile.yml           # Wszystkie taski
├── deploy/
│   └── quadlet/          # Auto-generowane pliki
├── .env.local            # Lokalne zmienne
├── .env.prod             # Produkcyjne zmienne
├── .github/              # GitHub Actions
├── .gitlab-ci.yml        # GitLab CI
├── .gitea/               # Gitea Actions
├── .drone.yml            # Drone CI
└── Jenkinsfile           # Jenkins
```

## Szybki start

```bash
# 1. Lokalnie
cp .env.local .env
docker compose up

# 2. Generuj Quadlet dla prod
taskfile quadlet generate --env-file .env.prod

# 3. Deploy na VPS
taskfile --env prod run deploy
```

## Taski

### Development

| Task | Opis |
|------|------|
| `dev` | Start lokalnie (Docker Compose) |

### Build & Push

| Task | Opis |
|------|------|
| `build` | Zbuduj wszystkie obrazy |
| `build-app` | Zbuduj konkretną usługę (`--var SVC=app`) |
| `push` | Wyślij do registry |

### Deploy

| Task | Opis |
|------|------|
| `generate` | Wygeneruj pliki Quadlet |
| `deploy` | Pełny deploy (build → push → quadlet → deploy) |
| `deploy-quick` | Szybki deploy (tylko pull + restart) |
| `deploy-service` | Deploy jednej usługi |
| `upload-quadlets` | Tylko upload plików Quadlet |

### Operations (local + prod)

| Task | Opis |
|------|------|
| `status` | Status serwisów (`@local`/`@remote`) |
| `logs` | Logi (`--var SVC=app`, `@local`/`@remote`) |
| `restart` | Restart usługi (`@local`/`@remote`) |
| `stop` | Stop serwisów (`@local`/`@remote`) |
| `ram` | Użycie RAM na serwerze (prod) |
| `cleanup` | Wyczyść nieużywane obrazy (prod) |

### Setup

| Task | Opis |
|------|------|
| `setup-server` | Pierwsza konfiguracja serwera |

## Pipeline CI/CD

```yaml
pipeline:
  stages:
    - test       # build (walidacja Dockerfile)
    - build      # push (Docker in Docker)
    - generate   # quadlet + artifacts
    - deploy     # deploy-quick (manual)
```

## Generowanie CI/CD

```bash
# Generuj dla wszystkich platform
taskfile ci generate --all

# Generuj konkretną platformę
taskfile ci generate --platform github
taskfile ci generate --platform gitlab
```

## Quadlet - Auto-generowanie

```bash
# Wygeneruj z docker-compose.yml
taskfile quadlet generate \
  --compose docker-compose.yml \
  --env-file .env.prod \
  -o deploy/quadlet

# Efekt:
# deploy/quadlet/app.container
# deploy/quadlet/api.container
# deploy/quadlet/network.network
# deploy/quadlet/volume.volume
```

## Workflow deploy

### 1. Lokalny development
```bash
taskfile run dev          # Start
taskfile run logs         # Logi
taskfile run stop         # Stop
```

### 2. Build & Test
```bash
taskfile run build
taskfile run push
```

### 3. Generuj Quadlet
```bash
taskfile run generate
```

### 4. Deploy na prod
```bash
# Pełny deploy
taskfile --env prod run deploy

# Lub szybki (tylko pull + restart)
taskfile --env prod run deploy-quick

# Deploy konkretnej usługi
taskfile --env prod run deploy-service --var SVC=app
```

## Szczegóły implementacji

### docker-compose.yml jako source of truth

```yaml
# docker-compose.yml
services:
  app:
    image: ${REGISTRY}/codereview-app:${TAG}
    ports:
      - "${APP_PORT}:3000"
    environment:
      - API_URL=${API_URL}
```

### .env.local vs .env.prod

```bash
# .env.local
APP_PORT=3000
API_URL=http://localhost:8001

# .env.prod  
APP_PORT=80
API_URL=https://api.codereview.pl
```

### Quadlet generowanie

Taskfile automatycznie konwertuje:
- `services` → `.container` files
- `networks` → `.network` files
- `volumes` → `.volume` files
- `depends_on` → `After=/Requires=` in `[Unit]`

## Wszystkie platformy CI/CD

| Platforma | Plik | Generowanie |
|-----------|------|-------------|
| GitHub Actions | `.github/workflows/deploy.yml` | `taskfile ci generate --platform github` |
| GitLab CI | `.gitlab-ci.yml` | `taskfile ci generate --platform gitlab` |
| Gitea | `.gitea/workflows/deploy.yml` | `taskfile ci generate --platform gitea` |
| Drone | `.drone.yml` | `taskfile ci generate --platform drone` |
| Jenkins | `Jenkinsfile` | `taskfile ci generate --platform jenkins` |
| Makefile | `Makefile` | `taskfile ci generate --platform make` |

## Kiedy użyć tego przykładu?

✅ Real-world produkcyjne projekty  
✅ Kompletne CI/CD z wieloma platformami  
✅ Quadlet/Podman deploy  
✅ Single source of truth (docker-compose)  

## Następne kroki

Zobacz inne przykłady:
- [minimal/](../minimal/) - Najprostszy start
- [saas-app/](../saas-app/) - SaaS ze staging
- [multiplatform/](../multiplatform/) - Web + Desktop
