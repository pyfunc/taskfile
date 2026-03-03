"""Scaffold templates for `taskfile init`."""

TEMPLATES: dict[str, str] = {}

TEMPLATES["minimal"] = """\
version: "1"
name: my-app
description: Minimal Taskfile

variables:
  APP_NAME: my-app

environments:
  local:
    container_runtime: docker
    compose_command: docker compose

  prod:
    ssh_host: your-server.example.com
    ssh_user: deploy
    container_runtime: podman

tasks:
  build:
    desc: Build the application
    cmds:
      - ${COMPOSE} build

  deploy:
    desc: Deploy to target environment
    deps: [build]
    cmds:
      - ${COMPOSE} up -d

  logs:
    desc: View application logs
    cmds:
      - ${COMPOSE} logs -f

  status:
    desc: Show running services
    cmds:
      - ${COMPOSE} ps
"""

TEMPLATES["web"] = """\
version: "1"
name: web-app
description: Web app with Docker Compose + Traefik

variables:
  APP_NAME: web-app
  IMAGE: ghcr.io/myorg/web-app
  TAG: latest
  DOMAIN: app.example.com

environments:
  local:
    container_runtime: docker
    compose_command: docker compose
    variables:
      DOMAIN: ${APP_NAME}.localhost

  staging:
    ssh_host: staging.example.com
    ssh_user: deploy
    container_runtime: docker
    compose_command: docker compose
    variables:
      DOMAIN: staging.example.com

  prod:
    ssh_host: prod.example.com
    ssh_user: deploy
    container_runtime: podman
    variables:
      DOMAIN: app.example.com

tasks:
  build:
    desc: Build Docker image
    cmds:
      - docker build -t ${IMAGE}:${TAG} .

  push:
    desc: Push image to registry
    deps: [build]
    cmds:
      - docker push ${IMAGE}:${TAG}

  deploy-local:
    desc: Deploy locally with Docker Compose
    env: [local]
    cmds:
      - docker compose up -d --build
      - echo "✅ ${APP_NAME} → http://${DOMAIN}"

  deploy-remote:
    desc: Deploy to remote server via SSH
    env: [staging, prod]
    cmds:
      - "@remote ${RUNTIME} pull ${IMAGE}:${TAG}"
      - "@remote systemctl --user restart ${APP_NAME}"
      - echo "✅ ${APP_NAME} → https://${DOMAIN}"

  deploy:
    desc: Smart deploy — picks local or remote based on env
    deps: [push]
    cmds:
      - echo "Deploying ${APP_NAME} to ${ENV}..."

  logs:
    desc: View logs
    cmds:
      - ${COMPOSE} logs -f ${APP_NAME}

  logs-remote:
    desc: View remote logs
    env: [staging, prod]
    cmds:
      - "@remote journalctl --user -u ${APP_NAME} -f"

  status:
    desc: Check service status
    cmds:
      - ${COMPOSE} ps

  stop:
    desc: Stop services
    cmds:
      - ${COMPOSE} down

  clean:
    desc: Remove unused images and volumes
    cmds:
      - docker image prune -f
      - docker volume prune -f
"""

TEMPLATES["podman"] = """\
version: "1"
name: podman-app
description: Podman Quadlet + Traefik — optimized for low-RAM servers

variables:
  APP_NAME: my-app
  IMAGE: ghcr.io/myorg/my-app
  TAG: latest
  DOMAIN: app.example.com
  QUADLET_DIR: /etc/containers/systemd

environments:
  local:
    container_runtime: docker
    compose_command: docker compose
    variables:
      DOMAIN: ${APP_NAME}.localhost

  prod:
    ssh_host: vps.example.com
    ssh_user: deploy
    ssh_key: ~/.ssh/id_ed25519
    container_runtime: podman
    service_manager: quadlet
    variables:
      QUADLET_DIR: ~/.config/containers/systemd

tasks:
  build:
    desc: Build image
    cmds:
      - docker build -t ${IMAGE}:${TAG} .

  push:
    desc: Push to registry
    deps: [build]
    cmds:
      - docker push ${IMAGE}:${TAG}

  deploy-local:
    desc: Local development
    env: [local]
    cmds:
      - docker compose up -d --build
      - echo "✅ http://${APP_NAME}.localhost"

  deploy-quadlet:
    desc: Deploy Quadlet unit to server
    env: [prod]
    cmds:
      - scp deploy/${APP_NAME}.container ${DEPLOY_USER}@${SSH_HOST}:${QUADLET_DIR}/
      - "@remote systemctl --user daemon-reload"
      - "@remote systemctl --user restart ${APP_NAME}"
      - echo "✅ https://${DOMAIN}"

  deploy:
    desc: Build, push, deploy
    deps: [push]
    cmds:
      - echo "Deploying ${APP_NAME}:${TAG} to ${ENV}"

  pull-remote:
    desc: Pull latest image on server
    env: [prod]
    cmds:
      - "@remote podman pull ${IMAGE}:${TAG}"

  restart-remote:
    desc: Restart service on server
    env: [prod]
    cmds:
      - "@remote systemctl --user restart ${APP_NAME}"

  logs-remote:
    desc: View remote journald logs
    env: [prod]
    cmds:
      - "@remote journalctl --user -u ${APP_NAME} -f"

  status-remote:
    desc: Remote service status
    env: [prod]
    cmds:
      - "@remote systemctl --user status ${APP_NAME}"
      - "@remote podman ps --filter name=${APP_NAME}"

  cleanup-remote:
    desc: Clean unused images on server (saves RAM/disk)
    env: [prod]
    cmds:
      - "@remote podman image prune -af"
      - "@remote podman volume prune -f"
"""

TEMPLATES["full"] = """\
version: "1"
name: my-project
description: >
  Full Taskfile example with multi-environment deploy,
  Docker + Podman support, and CI/CD integration.

default_env: local

variables:
  APP_NAME: my-project
  IMAGE: ghcr.io/myorg/my-project
  TAG: latest
  DOMAIN: my-project.example.com

environments:
  local:
    container_runtime: docker
    compose_command: docker compose
    variables:
      DOMAIN: ${APP_NAME}.localhost
      TAG: dev

  staging:
    ssh_host: staging.example.com
    ssh_user: deploy
    ssh_port: 22
    ssh_key: ~/.ssh/id_ed25519
    container_runtime: docker
    compose_command: docker compose
    variables:
      DOMAIN: staging.example.com

  prod:
    ssh_host: prod.example.com
    ssh_user: deploy
    ssh_key: ~/.ssh/id_ed25519
    container_runtime: podman
    service_manager: quadlet
    variables:
      DOMAIN: my-project.example.com

# ─── Tasks ────────────────────────────────────────────

tasks:

  # ─── Build ────────────────────────────────────
  build:
    desc: Build Docker image
    cmds:
      - docker build -t ${IMAGE}:${TAG} .

  push:
    desc: Push image to container registry
    deps: [build]
    cmds:
      - docker push ${IMAGE}:${TAG}

  test:
    desc: Run tests
    cmds:
      - docker compose run --rm app pytest
    ignore_errors: false

  lint:
    desc: Run linter
    cmds:
      - docker compose run --rm app ruff check .
    ignore_errors: true

  # ─── Deploy ───────────────────────────────────
  deploy-local:
    desc: Start local dev environment
    env: [local]
    cmds:
      - docker compose up -d --build
      - echo "✅ ${APP_NAME} → http://${DOMAIN}"

  deploy-remote:
    desc: Deploy to remote (staging/prod)
    env: [staging, prod]
    cmds:
      - "@remote ${RUNTIME} pull ${IMAGE}:${TAG}"
      - "@remote systemctl --user restart ${APP_NAME}"
      - echo "✅ ${APP_NAME} → https://${DOMAIN}"

  deploy:
    desc: Full deploy pipeline
    deps: [test, push]
    cmds:
      - echo "🚀 Deploying ${APP_NAME}:${TAG} to ${ENV}"

  # ─── Release ──────────────────────────────────
  release:
    desc: Tag, build, push, deploy to prod
    cmds:
      - git tag -a ${TAG} -m "Release ${TAG}"
      - git push origin ${TAG}
      - docker build -t ${IMAGE}:${TAG} .
      - docker push ${IMAGE}:${TAG}
      - echo "📦 Released ${APP_NAME}:${TAG}"

  # ─── Operations ───────────────────────────────
  logs:
    desc: View logs (local)
    env: [local]
    cmds:
      - docker compose logs -f

  logs-remote:
    desc: View logs (remote)
    env: [staging, prod]
    cmds:
      - "@remote journalctl --user -u ${APP_NAME} -f"

  status:
    desc: Service status (local)
    env: [local]
    cmds:
      - docker compose ps

  status-remote:
    desc: Service status (remote)
    env: [staging, prod]
    cmds:
      - "@remote systemctl --user status ${APP_NAME}"
      - "@remote ${RUNTIME} ps --filter name=${APP_NAME}"

  stop:
    desc: Stop all services (local)
    env: [local]
    cmds:
      - docker compose down

  stop-remote:
    desc: Stop service (remote)
    env: [staging, prod]
    cmds:
      - "@remote systemctl --user stop ${APP_NAME}"

  restart-remote:
    desc: Restart service (remote)
    env: [staging, prod]
    cmds:
      - "@remote systemctl --user restart ${APP_NAME}"

  # ─── Maintenance ──────────────────────────────
  cleanup:
    desc: Remove unused Docker resources
    cmds:
      - docker image prune -af
      - docker volume prune -f
      - docker builder prune -f
      - echo "🧹 Cleaned up local Docker resources"

  cleanup-remote:
    desc: Clean unused images on server
    env: [staging, prod]
    cmds:
      - "@remote ${RUNTIME} image prune -af"
      - "@remote ${RUNTIME} volume prune -f"

  # ─── Setup ────────────────────────────────────
  setup-server:
    desc: Initial server setup (install Podman, create dirs)
    env: [prod]
    cmds:
      - "@remote sudo apt-get update && sudo apt-get install -y podman"
      - "@remote mkdir -p ~/.config/containers/systemd"
      - "@remote podman network create proxy 2>/dev/null || true"
      - "@remote loginctl enable-linger $(whoami)"
      - echo "✅ Server ready for Podman Quadlet"

  upload-quadlet:
    desc: Upload Quadlet files to server
    env: [prod]
    cmds:
      - scp deploy/*.container deploy/*.network ${SSH_USER}@${SSH_HOST}:~/.config/containers/systemd/
      - "@remote systemctl --user daemon-reload"
      - echo "✅ Quadlet files uploaded"
"""


def generate_taskfile(template: str = "full") -> str:
    """Generate a Taskfile.yml from a template."""
    if template not in TEMPLATES:
        raise ValueError(f"Unknown template: {template}. Available: {list(TEMPLATES.keys())}")
    return TEMPLATES[template]


# ─── codereview template ────────────────────────────

TEMPLATES["codereview"] = """\
version: "1"
name: codereview
description: >
  codereview.pl — 3-stage deployment.
  Local: Docker Compose + Traefik.
  Prod: Podman Quadlet + Traefik on 512MB VPS.
  Single docker-compose.yml as source of truth,
  .env files for per-environment differences.

default_env: local

variables:
  APP_NAME: codereview
  REGISTRY: ghcr.io/softreck
  TAG: latest
  PROXY_NETWORK: proxy

environments:
  local:
    container_runtime: docker
    compose_command: docker compose
    compose_file: docker-compose.yml
    env_file: .env.local
    service_manager: compose
    variables:
      DOMAIN: localhost
      TLS_ENABLED: "false"
      ENTRYPOINT: web

  staging:
    ssh_host: staging.codereview.pl
    ssh_user: deploy
    ssh_key: ~/.ssh/id_ed25519
    container_runtime: docker
    compose_command: docker compose
    compose_file: docker-compose.yml
    env_file: .env.staging
    service_manager: compose
    variables:
      DOMAIN: staging.codereview.pl
      TLS_ENABLED: "true"
      ENTRYPOINT: websecure

  prod:
    ssh_host: codereview.pl
    ssh_user: deploy
    ssh_key: ~/.ssh/id_ed25519
    container_runtime: podman
    service_manager: quadlet
    compose_file: docker-compose.yml
    env_file: .env.prod
    quadlet_dir: deploy/quadlet
    quadlet_remote_dir: ~/.config/containers/systemd
    variables:
      DOMAIN: codereview.pl
      TLS_ENABLED: "true"
      ENTRYPOINT: websecure
      CERT_RESOLVER: le

# ─── Tasks ──────────────────────────────────────────

tasks:

  # ─── Build ────────────────────────────────────
  build:
    desc: Build all images
    cmds:
      - docker compose --env-file .env.local build

  build-app:
    desc: Build single app (--var APP=web)
    cmds:
      - docker build -t ${REGISTRY}/${APP}:${TAG} ./apps/${APP}

  push:
    desc: Push all images to registry
    deps: [build]
    cmds:
      - docker compose --env-file .env.local push

  push-app:
    desc: Push single app (--var APP=web)
    deps: [build-app]
    cmds:
      - docker push ${REGISTRY}/${APP}:${TAG}

  test:
    desc: Run tests
    cmds:
      - docker compose --env-file .env.local run --rm app pytest

  # ─── Local Development ────────────────────────
  dev:
    desc: Start local dev with Docker Compose + Traefik
    env: [local]
    cmds:
      - docker compose --env-file .env.local up -d --build
      - echo "✅ codereview.pl running locally"
      - echo "   http://app.localhost"
      - echo "   http://traefik.localhost:8080 (dashboard)"

  dev-down:
    desc: Stop local dev
    env: [local]
    cmds:
      - docker compose --env-file .env.local down

  dev-logs:
    desc: Follow local logs
    env: [local]
    cmds:
      - docker compose --env-file .env.local logs -f

  dev-restart:
    desc: Restart single service (--var APP=web)
    env: [local]
    cmds:
      - docker compose --env-file .env.local restart ${APP}

  # ─── Staging Deploy ───────────────────────────
  deploy-staging:
    desc: Deploy to staging via Docker Compose over SSH
    env: [staging]
    deps: [push]
    cmds:
      - "@remote cd /opt/codereview && docker compose --env-file .env.staging pull"
      - "@remote cd /opt/codereview && docker compose --env-file .env.staging up -d"
      - echo "✅ Deployed to staging.codereview.pl"

  # ─── Production Deploy (Quadlet) ──────────────
  quadlet-generate:
    desc: Generate Quadlet files from docker-compose.yml + .env.prod
    cmds:
      - echo "Generating Quadlet files..."
    # NOTE: Use 'taskfile quadlet generate --env-file .env.prod' instead
    # This task is a placeholder — the real work is done by the quadlet CLI

  deploy-prod:
    desc: Full production deploy — push, generate quadlet, upload, restart
    env: [prod]
    deps: [push]
    cmds:
      - echo "🚀 Deploying to production..."
      - "@remote podman pull ${REGISTRY}/app:${TAG}"
      - "@remote podman pull ${REGISTRY}/web:${TAG}"
      - "@remote systemctl --user daemon-reload"
      - "@remote systemctl --user restart app"
      - "@remote systemctl --user restart web"
      - "@remote podman image prune -f"
      - echo "✅ Deployed to codereview.pl"

  deploy-quadlet:
    desc: Generate + upload Quadlet files to prod
    env: [prod]
    cmds:
      - echo "Generating Quadlet files from docker-compose.yml..."
    # Run: taskfile quadlet generate --env-file .env.prod
    # Then: taskfile --env prod quadlet upload

  # ─── Operations ───────────────────────────────
  status:
    desc: Show status on target environment
    env: [staging, prod]
    cmds:
      - "@remote ${RUNTIME} ps --format 'table {{.Names}}\\t{{.Status}}\\t{{.Ports}}'"

  logs:
    desc: View logs on target (--var APP=web)
    env: [staging, prod]
    cmds:
      - "@remote journalctl --user -u ${APP} -f --no-pager -n 100"

  ram:
    desc: Check RAM usage on server
    env: [staging, prod]
    cmds:
      - "@remote free -h"
      - "@remote ${RUNTIME} stats --no-stream --format 'table {{.Name}}\\t{{.MemUsage}}'"

  cleanup:
    desc: Clean unused images on server
    env: [staging, prod]
    cmds:
      - "@remote ${RUNTIME} image prune -af"
      - "@remote ${RUNTIME} volume prune -f"
      - echo "🧹 Cleaned"

  # ─── Initial Setup ───────────────────────────
  setup-server:
    desc: First-time server provisioning
    env: [prod]
    cmds:
      - "@remote sudo apt-get update && sudo apt-get install -y podman"
      - "@remote mkdir -p ~/.config/containers/systemd"
      - "@remote podman network create ${PROXY_NETWORK} 2>/dev/null || true"
      - "@remote loginctl enable-linger $(whoami)"
      - echo "✅ Server ready for Podman Quadlet"

  # ─── Release ──────────────────────────────────
  release:
    desc: Tag + full deploy pipeline
    cmds:
      - git tag -a ${TAG} -m 'Release ${TAG}'
      - git push origin ${TAG}
      - echo "📦 Release ${TAG} created"
"""
