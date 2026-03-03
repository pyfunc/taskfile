# Taskfile Examples

## minimal/
Simplest possible Taskfile: test, build, run. No environments, no SSH.

## saas-app/
Multi-env SaaS: local Docker + staging + prod Podman Quadlet with pipeline.

## codereview.pl/
Complete real-world project with docker-compose.yml as single source of truth,
20+ tasks, 4 pipeline stages, and generated CI/CD for all 6 platforms:
GitHub Actions, GitLab CI, Gitea, Drone, Jenkins, Makefile.

## Taskfile.softreck.yml
Multi-project deployment for Softreck organization (wronai, prototypowanie, portigen).
