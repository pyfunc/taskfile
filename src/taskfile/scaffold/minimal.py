TEMPLATE = """\
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
