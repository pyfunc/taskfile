# IaC Nomad — HashiCorp Workload Orchestration + Markpact

**Cały projekt Nomad w jednym pliku README.md — wypakuj i uruchom przez Taskfile.**

## 📋 Co to jest?

HashiCorp Nomad — lekki orkiestrator workloadów (kontenery, VMs, binaria).
Multi-environment, job planning, blue-green/canary deploys, zintegrowane z `taskfile`.

## Features covered

- **`dir`** — tasks run inside `nomad/` directory
- **`env_file`** — per-environment Nomad cluster config
- **Multi-environment** — dev (local agent), staging, prod
- **Canary deploys** — built-in with Nomad
- **Consul integration** — service discovery

## 🎯 Workflow

```bash
# 1. Wypakowanie projektu
markpact README.md && cd sandbox

# 2. Validate
taskfile --env dev run validate

# 3. Plan
taskfile --env dev run plan

# 4. Deploy
taskfile --env dev run deploy

# 5. Status
taskfile --env dev run status

# 6. Logs
taskfile --env dev run logs

# 7. Stop
taskfile --env dev run stop
```

## 🔧 Dostępne komendy

| Komenda | Opis |
|---------|------|
| `taskfile run validate` | Validate job specification |
| `taskfile run plan` | Preview job changes |
| `taskfile run deploy` | Deploy/run job |
| `taskfile run stop` | Stop job |
| `taskfile run status` | Show job status |
| `taskfile run logs` | View task logs |
| `taskfile run allocs` | Show allocations |
| `taskfile run scale` | Scale task group |
| `taskfile run promote` | Promote canary deployment |
| `taskfile run revert` | Revert to previous version |
| `taskfile run exec` | Execute command in allocation |
| `taskfile run clean` | Purge stopped jobs |

---

## Pliki projektu (markpact)

### Taskfile.yml — konfiguracja tasków

```markpact:file path=Taskfile.yml
version: "1"
name: nomad-workloads
description: "HashiCorp Nomad: workload orchestration with canary deploys"

variables:
  NOMAD_DIR: nomad
  JOB_FILE: web.nomad.hcl
  JOB_NAME: web
  TASK_GROUP: web
  REPLICAS: "2"

environments:
  dev:
    env_file: .env.dev
    variables:
      NOMAD_ADDR: http://localhost:4646
      DATACENTER: dc1
      REPLICAS: "1"
      IMAGE_TAG: dev

  staging:
    env_file: .env.staging
    variables:
      NOMAD_ADDR: https://nomad-staging.example.com
      DATACENTER: staging-dc1
      REPLICAS: "2"
      IMAGE_TAG: staging

  prod:
    env_file: .env.prod
    variables:
      NOMAD_ADDR: https://nomad-prod.example.com
      DATACENTER: prod-dc1
      REPLICAS: "5"
      IMAGE_TAG: latest

environment_groups:
  all-prod:
    members: [prod]
    strategy: canary
    canary_count: 1

tasks:

  validate:
    desc: Validate job specification
    dir: ${NOMAD_DIR}
    cmds:
      - nomad job validate ${JOB_FILE}

  plan:
    desc: Preview job changes (dry-run)
    dir: ${NOMAD_DIR}
    cmds:
      - nomad job plan -var="datacenter=${DATACENTER}" -var="image_tag=${IMAGE_TAG}" -var="count=${REPLICAS}" ${JOB_FILE}
    ignore_errors: true

  deploy:
    desc: Deploy/run job
    dir: ${NOMAD_DIR}
    deps: [validate]
    cmds:
      - nomad job run -var="datacenter=${DATACENTER}" -var="image_tag=${IMAGE_TAG}" -var="count=${REPLICAS}" ${JOB_FILE}

  stop:
    desc: Stop job
    cmds:
      - nomad job stop ${JOB_NAME}

  status:
    desc: Show job status
    cmds:
      - nomad job status ${JOB_NAME}

  logs:
    desc: View task logs (latest allocation)
    cmds:
      - nomad alloc logs -job ${JOB_NAME}

  allocs:
    desc: Show all allocations
    cmds:
      - nomad job allocs ${JOB_NAME}

  scale:
    desc: Scale task group (use --var REPLICAS=N)
    cmds:
      - nomad job scale ${JOB_NAME} ${TASK_GROUP} ${REPLICAS}

  promote:
    desc: Promote canary deployment
    cmds:
      - nomad deployment promote -job ${JOB_NAME}

  revert:
    desc: Revert to previous job version
    cmds:
      - nomad job revert ${JOB_NAME} 0

  exec:
    desc: Execute command in latest allocation
    cmds:
      - nomad alloc exec -job ${JOB_NAME} /bin/sh

  clean:
    desc: Purge stopped jobs
    cmds:
      - nomad job stop -purge ${JOB_NAME} || true
      - nomad system gc
```

### nomad/web.nomad.hcl — Nomad job specification

```markpact:file path=nomad/web.nomad.hcl
variable "datacenter" {
  type    = string
  default = "dc1"
}

variable "image_tag" {
  type    = string
  default = "latest"
}

variable "count" {
  type    = number
  default = 2
}

job "web" {
  datacenters = [var.datacenter]
  type        = "service"

  update {
    max_parallel     = 1
    min_healthy_time = "30s"
    healthy_deadline = "5m"
    canary           = 1
    auto_revert      = true
    auto_promote     = false
  }

  group "web" {
    count = var.count

    network {
      port "http" {
        to = 8000
      }
    }

    service {
      name = "web"
      port = "http"
      tags = ["traefik.enable=true"]

      check {
        type     = "http"
        path     = "/health"
        interval = "10s"
        timeout  = "2s"
      }
    }

    task "app" {
      driver = "docker"

      config {
        image = "ghcr.io/myorg/web:${var.image_tag}"
        ports = ["http"]
      }

      resources {
        cpu    = 256
        memory = 256
      }

      env {
        PORT = "${NOMAD_PORT_http}"
      }
    }
  }
}
```

### .env.dev

```markpact:file path=.env.dev
NOMAD_ADDR=http://localhost:4646
NOMAD_TOKEN=
```

---

## 📚 Dokumentacja

- [Nomad Docs](https://developer.hashicorp.com/nomad/docs)
- [Nomad Job Specification](https://developer.hashicorp.com/nomad/docs/job-specification)
- [Nomad Tutorials](https://developer.hashicorp.com/nomad/tutorials)

**Licencja:** MIT
