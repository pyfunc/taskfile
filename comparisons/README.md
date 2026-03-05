# Taskfile vs Other Tools — Comparison

This document compares `taskfile` with similar task runners and automation tools.

## Individual Comparisons

- [Taskfile vs Just](taskfile-vs-just.md) — Simple command runner (Rust)
- [Taskfile vs Task (go-task)](taskfile-vs-go-task.md) — Go-based task runner
- [Taskfile vs Make](taskfile-vs-make.md) — Classic build tool
- [Taskfile vs Ansible](taskfile-vs-ansible.md) — IT automation platform
- [Taskfile vs Dagger](taskfile-vs-dagger.md) — Containerized CI/CD
- [Taskfile vs Mage](taskfile-vs-mage.md) — Go-coded tasks

## Overview

```
taskfile ≈ Make + Ansible-lite + Dagger orchestration + Fleet management + CI/CD generation
```

## Full Feature Matrix

| Feature | Just | Task (go-task) | Make | Mage | Dagger | Ansible | **Taskfile** |
|---------|------|----------------|------|------|--------|---------|--------------| 
| YAML config | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ | ✅ |
| Task dependencies | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ |
| Parallel deps | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ |
| Variables | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Environments** | ❌ | ❌ | ❌ | ❌ | ❌ | Manual | ✅ |
| **Environment groups** | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| **SSH `@remote` execution** | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| **SSH embedded (paramiko)** | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| **Fleet management** | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ (100+) | ✅ (<50) |
| **`pipeline` section** | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ |
| **CI/CD generation** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ (6 platforms) |
| **`condition` on tasks** | ❌ | ✅ | ❌ | ✅ | ❌ | ✅ | ✅ |
| **`dir` (working_dir)** | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| **`stage` auto-inference** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| **`env_file` per env** | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| **`include` (import files)** | ❌ | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ |
| **Quadlet generation** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| **VPS setup** | ❌ | ❌ | ❌ | ❌ | ❌ | ⚠️ | ✅ |
| **Registry auth** | ❌ | ❌ | ❌ | ❌ | Manual | ❌ | ✅ |
| **Platforms matrix** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| File-based deps | ❌ | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ |
| Containerized builds | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| Idempotent modules | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| Learning curve | Low | Low | Medium | Medium | Steep | Steep | Low |

---

## When to Choose Each Tool

```
┌────────────────────────────────────────────────────────────────┐
│  Simple project, small team, local tasks only                  │
│  → Just or Make                                                │
├────────────────────────────────────────────────────────────────┤
│  Complex builds, Go-centric team, type safety                  │
│  → Mage or Task (go-task)                                      │
├────────────────────────────────────────────────────────────────┤
│  Containerized CI/CD, reproducible builds                      │
│  → Dagger + Taskfile (orchestration layer)                     │
├────────────────────────────────────────────────────────────────┤
│  100+ servers, complex provisioning, idempotency               │
│  → Ansible (+ Taskfile for daily ops)                          │
├────────────────────────────────────────────────────────────────┤
│  <50 devices, edge/IoT fleets, multi-env deploys               │
│  → Taskfile ✅                                                 │
├────────────────────────────────────────────────────────────────┤
│  CI/CD generation, Podman Quadlet, VPS setup, multi-registry   │
│  → Taskfile ✅                                                 │
├────────────────────────────────────────────────────────────────┤
│  Kubernetes + Helm + Terraform + AWS multi-region               │
│  → Taskfile ✅ (see examples/)                                 │
└────────────────────────────────────────────────────────────────┘
```

---

## Unique Taskfile Features

| Feature | Description | Use Case |
|---------|-------------|----------|
| `@remote` prefix | SSH execution on target environment | Deploy to remote servers |
| SSH embedded (paramiko) | Native Python SSH — no subprocess | Faster, connection pooling |
| `environments` + `environment_defaults` | Multi-env config abstraction | local / staging / prod |
| `environment_groups` | Fleet deploy with strategies | rolling / canary / parallel |
| `pipeline` section | Declarative CI/CD stages | `when`, `docker_in_docker`, `artifacts` |
| `taskfile ci generate` | Generate CI/CD configs from pipeline | GitHub, GitLab, Gitea, Drone, Jenkins, Makefile |
| `condition` on tasks | Run task only if condition met | `docker info >/dev/null 2>&1` |
| `dir` (working_dir) | Per-task working directory | Monorepo: `dir: services/api` |
| `stage` auto-inference | Auto-build pipeline from task fields | No explicit pipeline section needed |
| `env_file` per environment | Load `.env.prod`, `.env.staging` | Secrets per environment |
| `include` | Import tasks from other Taskfile files | Split large configs |
| `platforms` matrix | Build/deploy per platform | web + desktop + mobile-bff |
| Quadlet generator | docker-compose → Podman systemd | Low-RAM VPS deployments |
| VPS setup | One-command server provisioning | `taskfile setup <IP>` |
| Registry auth | Interactive token setup | PyPI, npm, Docker, GitHub, crates.io |
| Fleet commands | `status`, `repair`, `list`, `deploy` | Monitor edge devices |

---

## Summary Matrix

| Use Case | Recommended Tool |
|----------|------------------|
| C/C++ builds with file deps | Make |
| Simple per-project recipes | Just |
| Go-centric build logic | Mage |
| Containerized CI pipelines | Dagger |
| 100+ host provisioning | Ansible |
| **Edge fleets, Podman, multi-env** | **Taskfile** |
| **K8s + Helm + Terraform** | **Taskfile** |
| **CI/CD generation (6 platforms)** | **Taskfile** |
| **Multi-registry publishing** | **Taskfile** |

---

## Integration Patterns

### Taskfile + Make
```makefile
# Makefile — thin wrapper for teams that expect `make`
deploy:
	taskfile --env prod run deploy
test:
	taskfile run test
```

### Taskfile + Ansible
```yaml
tasks:
  provision:
    cmds: [ansible-playbook -i inventory.yml setup.yml]
  deploy:
    cmds: ["@remote podman pull ${IMAGE}:${TAG}"]
```

### Taskfile + Dagger
```yaml
tasks:
  build:
    cmds: [dagger call build --source=.]
  deploy:
    deps: [build]
    cmds: ["@remote systemctl --user restart ${APP}"]
```

### Taskfile + Terraform
```yaml
tasks:
  plan:
    dir: terraform/
    cmds: [terraform plan -out=tfplan]
  apply:
    dir: terraform/
    deps: [plan]
    cmds: [terraform apply tfplan]
```

### Taskfile + Helm (Kubernetes)
```yaml
tasks:
  deploy:
    cmds:
      - kubectl config use-context ${CONTEXT}
      - helm upgrade --install ${APP} ./helm/ --set image.tag=${TAG}
```

### Taskfile + External Scripts
```yaml
tasks:
  build:
    cmds: [./scripts/build.sh]          # Shell script
  deploy:
    cmds: [python scripts/deploy.py]    # Python script
  test:
    cmds: [scripts/test.py]             # Executable Python
```
