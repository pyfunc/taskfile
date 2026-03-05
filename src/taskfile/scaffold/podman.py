TEMPLATE = """\
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
