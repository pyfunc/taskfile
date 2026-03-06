# IaC GCP Deployment Manager — Google Cloud Native IaC + Markpact

**Cały projekt GCP Deployment Manager w jednym pliku README.md — wypakuj i uruchom przez Taskfile.**

## 📋 Co to jest?

Google Cloud Deployment Manager — natywne IaC dla GCP. YAML/Jinja2/Python templates,
multi-environment (dev/staging/prod), preview/create/update, zintegrowane z `taskfile`.

## Features covered

- **`env_file`** — per-environment GCP project config
- **`deps`** — validate before deploy
- **Templates** — Jinja2 + Python templates
- **Preview** — before create/update

## 🎯 Workflow

```bash
# 1. Wypakowanie projektu
markpact README.md && cd sandbox

# 2. Auth
taskfile run auth

# 3. Preview
taskfile --env dev run preview

# 4. Deploy
taskfile --env dev run create
taskfile --env prod run create

# 5. Update
taskfile --env dev run update

# 6. Status
taskfile --env dev run describe

# 7. Destroy
taskfile --env dev run delete
```

## 🔧 Dostępne komendy

| Komenda | Opis |
|---------|------|
| `taskfile run auth` | Authenticate with GCP |
| `taskfile run preview` | Preview deployment changes |
| `taskfile run create` | Create deployment |
| `taskfile run update` | Update existing deployment |
| `taskfile run delete` | Delete deployment |
| `taskfile run describe` | Describe deployment |
| `taskfile run list` | List all deployments |
| `taskfile run resources` | List deployment resources |
| `taskfile run validate` | Validate templates |
| `taskfile run clean` | Remove local artifacts |

---

## Pliki projektu (markpact)

### Taskfile.yml — konfiguracja tasków

```markpact:file path=Taskfile.yml
version: "1"
name: gcp-dm
description: "GCP Deployment Manager: native IaC for Google Cloud"

variables:
  TEMPLATES_DIR: templates
  DEPLOYMENT_PREFIX: myapp
  DEPLOYMENT_FILE: deployment.yaml

environments:
  dev:
    env_file: .env.dev
    variables:
      GCP_PROJECT: my-project-dev
      GCP_REGION: europe-west1
      DEPLOYMENT_NAME: ${DEPLOYMENT_PREFIX}-dev
      MACHINE_TYPE: e2-small

  staging:
    env_file: .env.staging
    variables:
      GCP_PROJECT: my-project-staging
      GCP_REGION: europe-west1
      DEPLOYMENT_NAME: ${DEPLOYMENT_PREFIX}-staging
      MACHINE_TYPE: e2-medium

  prod:
    env_file: .env.prod
    variables:
      GCP_PROJECT: my-project-prod
      GCP_REGION: europe-west1
      DEPLOYMENT_NAME: ${DEPLOYMENT_PREFIX}-prod
      MACHINE_TYPE: e2-standard-2

tasks:

  auth:
    desc: Authenticate with GCP
    cmds:
      - gcloud auth login
      - gcloud config set project ${GCP_PROJECT}
      - gcloud config set compute/region ${GCP_REGION}

  preview:
    desc: Preview deployment changes
    cmds:
      - >-
        gcloud deployment-manager deployments update ${DEPLOYMENT_NAME}
        --config ${DEPLOYMENT_FILE}
        --preview
        --project ${GCP_PROJECT}

  create:
    desc: Create deployment
    cmds:
      - >-
        gcloud deployment-manager deployments create ${DEPLOYMENT_NAME}
        --config ${DEPLOYMENT_FILE}
        --project ${GCP_PROJECT}

  update:
    desc: Update existing deployment
    cmds:
      - >-
        gcloud deployment-manager deployments update ${DEPLOYMENT_NAME}
        --config ${DEPLOYMENT_FILE}
        --project ${GCP_PROJECT}

  delete:
    desc: Delete deployment
    cmds:
      - >-
        gcloud deployment-manager deployments delete ${DEPLOYMENT_NAME}
        --project ${GCP_PROJECT}
        --quiet

  describe:
    desc: Describe deployment status
    cmds:
      - gcloud deployment-manager deployments describe ${DEPLOYMENT_NAME} --project ${GCP_PROJECT}

  list:
    desc: List all deployments
    cmds:
      - gcloud deployment-manager deployments list --project ${GCP_PROJECT}

  resources:
    desc: List resources in deployment
    cmds:
      - gcloud deployment-manager resources list --deployment ${DEPLOYMENT_NAME} --project ${GCP_PROJECT}

  validate:
    desc: Validate templates (dry-run create)
    cmds:
      - >-
        gcloud deployment-manager deployments create validate-test
        --config ${DEPLOYMENT_FILE}
        --project ${GCP_PROJECT}
        --preview
      - gcloud deployment-manager deployments delete validate-test --project ${GCP_PROJECT} --quiet
    ignore_errors: true

  clean:
    desc: Remove local artifacts
    cmds:
      - rm -f *.expanded
```

### deployment.yaml — GCP deployment config

```markpact:file path=deployment.yaml
imports:
  - path: templates/network.jinja
  - path: templates/instance.jinja

resources:
  - name: vpc-network
    type: templates/network.jinja
    properties:
      region: europe-west1

  - name: web-instance
    type: templates/instance.jinja
    properties:
      zone: europe-west1-b
      machineType: e2-small
      network: $(ref.vpc-network.selfLink)
      subnet: $(ref.vpc-network.subnetSelfLink)

outputs:
  - name: networkSelfLink
    value: $(ref.vpc-network.selfLink)
  - name: instanceIP
    value: $(ref.web-instance.natIP)
```

### templates/network.jinja — VPC network template

```markpact:file path=templates/network.jinja
resources:
  - name: {{ env["name"] }}
    type: compute.v1.network
    properties:
      autoCreateSubnetworks: false

  - name: {{ env["name"] }}-subnet
    type: compute.v1.subnetwork
    properties:
      region: {{ properties["region"] }}
      network: $(ref.{{ env["name"] }}.selfLink)
      ipCidrRange: 10.0.0.0/24

outputs:
  - name: selfLink
    value: $(ref.{{ env["name"] }}.selfLink)
  - name: subnetSelfLink
    value: $(ref.{{ env["name"] }}-subnet.selfLink)
```

### .env.dev

```markpact:file path=.env.dev
CLOUDSDK_CORE_PROJECT=my-project-dev
CLOUDSDK_COMPUTE_REGION=europe-west1
```

---

## 📚 Dokumentacja

- [GCP Deployment Manager Docs](https://cloud.google.com/deployment-manager/docs)
- [DM Templates](https://cloud.google.com/deployment-manager/docs/configuration/templates/define-template)
- [DM Examples](https://github.com/GoogleCloudPlatform/deploymentmanager-samples)

**Licencja:** MIT
