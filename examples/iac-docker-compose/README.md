# IaC Docker Compose — Container Orchestration + Markpact

**Cały projekt Docker Compose w jednym pliku README.md — wypakuj i uruchom przez Taskfile.**

## 📋 Co to jest?

Docker Compose jako IaC dla kontenerów — multi-environment (local/staging/prod),
build/up/down z reverse proxy (Traefik), zintegrowane z `taskfile`.

## Features covered

- **`env_file`** — per-environment configuration
- **`environment_groups`** — `all` for global operations
- **`deps`** — build before up
- **Profiles** — separate services for dev/prod
- **Traefik** — reverse proxy with auto-TLS

## 🎯 Workflow

```bash
# 1. Wypakowanie projektu
markpact README.md && cd sandbox

# 2. Konfiguracja
taskfile setup env

# 3. Lokalny dev
taskfile --env local run dev

# 4. Build + deploy
taskfile --env local run build
taskfile --env local run up

# 5. Deploy prod
taskfile --env prod run build
taskfile --env prod run up

# 6. Logi i status
taskfile --env local run logs
taskfile --env local run status

# 7. Stop
taskfile --env local run down
```

## 🔧 Dostępne komendy

| Komenda | Opis |
|---------|------|
| `taskfile run build` | Build all Docker images |
| `taskfile run up` | Start all services |
| `taskfile run down` | Stop and remove containers |
| `taskfile run dev` | Start with hot-reload |
| `taskfile run logs` | View service logs |
| `taskfile run status` | Show running containers |
| `taskfile run restart` | Restart services |
| `taskfile run exec` | Execute command in container |
| `taskfile run pull` | Pull latest images |
| `taskfile run prune` | Remove unused images/volumes |
| `taskfile run backup-volumes` | Backup Docker volumes |
| `taskfile run clean` | Full cleanup |

---

## Pliki projektu (markpact)

### Taskfile.yml — konfiguracja tasków

```markpact:file path=Taskfile.yml
version: "1"
name: compose-app
description: "Docker Compose: multi-env container orchestration with Traefik"

variables:
  COMPOSE: docker compose
  PROJECT_NAME: myapp
  TAG: latest

environments:
  local:
    env_file: .env.local
    variables:
      COMPOSE_FILE: docker-compose.yml
      COMPOSE_PROFILES: dev

  staging:
    env_file: .env.staging
    variables:
      COMPOSE_FILE: docker-compose.yml:docker-compose.staging.yml
      COMPOSE_PROFILES: staging

  prod:
    env_file: .env.prod
    variables:
      COMPOSE_FILE: docker-compose.yml:docker-compose.prod.yml
      COMPOSE_PROFILES: prod

tasks:

  build:
    desc: Build all Docker images
    cmds:
      - ${COMPOSE} -p ${PROJECT_NAME} build --parallel

  up:
    desc: Start all services (detached)
    deps: [build]
    cmds:
      - ${COMPOSE} -p ${PROJECT_NAME} up -d

  down:
    desc: Stop and remove containers
    cmds:
      - ${COMPOSE} -p ${PROJECT_NAME} down

  dev:
    desc: Start with hot-reload and logs
    cmds:
      - ${COMPOSE} -p ${PROJECT_NAME} up -d --build
      - echo "✅ Dev running at http://localhost:${PORT_WEB:-8000}"
      - ${COMPOSE} -p ${PROJECT_NAME} logs -f

  logs:
    desc: View service logs (last 50 lines)
    cmds:
      - ${COMPOSE} -p ${PROJECT_NAME} logs --tail 50 -f

  status:
    desc: Show running containers
    cmds:
      - ${COMPOSE} -p ${PROJECT_NAME} ps

  restart:
    desc: Restart all services
    cmds:
      - ${COMPOSE} -p ${PROJECT_NAME} restart

  exec:
    desc: Execute shell in web container
    cmds:
      - ${COMPOSE} -p ${PROJECT_NAME} exec web /bin/sh

  pull:
    desc: Pull latest base images
    cmds:
      - ${COMPOSE} -p ${PROJECT_NAME} pull

  prune:
    desc: Remove unused Docker resources
    cmds:
      - docker image prune -f
      - docker volume prune -f
      - docker network prune -f

  backup-volumes:
    desc: Backup Docker volumes
    cmds:
      - mkdir -p backups
      - docker run --rm -v ${PROJECT_NAME}_data:/data -v $(pwd)/backups:/backup alpine tar czf /backup/data-$(date +%Y%m%d).tar.gz -C /data .
      - echo "✅ Backup saved to backups/"

  clean:
    desc: Full cleanup (containers, images, volumes)
    cmds:
      - ${COMPOSE} -p ${PROJECT_NAME} down -v --rmi local
      - docker image prune -f
```

### docker-compose.yml — base config

```markpact:file path=docker-compose.yml
services:
  web:
    build:
      context: ./apps/web
      dockerfile: Dockerfile
    ports:
      - "${PORT_WEB:-8000}:8000"
    environment:
      - VERSION=${VERSION:-1.0.0}
      - DATABASE_URL=postgresql://app:secret@db:5432/myapp
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - ./apps/web:/app
    restart: unless-stopped

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: myapp
      POSTGRES_USER: app
      POSTGRES_PASSWORD: secret
    volumes:
      - db_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    ports:
      - "${PORT_REDIS:-6379}:6379"
    restart: unless-stopped

volumes:
  db_data:
```

### docker-compose.prod.yml — production overrides

```markpact:file path=docker-compose.prod.yml
services:
  web:
    volumes: []
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '1.0'
          memory: 512M
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.web.rule=Host(`${WEB_DOMAIN}`)"
      - "traefik.http.routers.web.tls.certresolver=letsencrypt"

  traefik:
    image: traefik:v3.0
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - traefik_certs:/letsencrypt
    command:
      - "--providers.docker=true"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.letsencrypt.acme.email=${ACME_EMAIL}"
      - "--certificatesresolvers.letsencrypt.acme.storage=/letsencrypt/acme.json"
      - "--certificatesresolvers.letsencrypt.acme.tlschallenge=true"
    restart: unless-stopped

volumes:
  traefik_certs:
```

### .env.local

```markpact:file path=.env.local
PORT_WEB=8000
PORT_REDIS=6379
VERSION=1.0.0-dev
```

### .env.prod

```markpact:file path=.env.prod
PORT_WEB=8000
VERSION=1.0.0
WEB_DOMAIN=app.example.com
ACME_EMAIL=admin@example.com
```

---

## 📚 Dokumentacja

- [Docker Compose Docs](https://docs.docker.com/compose/)
- [Traefik Docs](https://doc.traefik.io/traefik/)

**Licencja:** MIT
