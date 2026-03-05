# Kubernetes Deploy — Helm + Multi-Cluster

Deploy do Kubernetes z Helm, multi-cluster (staging + prod-eu + prod-us), canary strategy.

## Features covered

- **Multi-cluster environments** — minikube, staging, prod-eu, prod-us
- **`environment_defaults`** — shared container_runtime
- **`environment_groups`** — `all-prod` (canary), `global` (rolling)
- **`pipeline`** with `when: manual` for prod deploy
- **Helm** — upgrade, diff, rollback, history
- **K8s ops** — status, logs, exec, scale, restart

## Usage

```bash
# Local development (minikube)
taskfile --env local run dev

# Deploy to staging
taskfile --env staging run helm-deploy --var TAG=v1.0.0

# Preview changes before deploy
taskfile --env prod-eu run helm-diff --var TAG=v1.0.0

# Deploy to all prod clusters (canary: eu first, then us)
taskfile -G all-prod run helm-deploy --var TAG=v1.0.0

# Rollback prod-eu
taskfile --env prod-eu run helm-rollback

# Scale prod-us
taskfile --env prod-us run k8s-scale --var REPLICAS=10

# CI pipeline
taskfile ci generate --target github
taskfile ci run
```
