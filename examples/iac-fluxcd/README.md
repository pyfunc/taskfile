# IaC FluxCD — GitOps for Kubernetes + Markpact

**Cały projekt FluxCD w jednym pliku README.md — wypakuj i uruchom przez Taskfile.**

## 📋 Co to jest?

FluxCD — GitOps toolkit dla Kubernetes (CNCF project). Automatyczna synchronizacja
z Git repo, Helm releases, Kustomize, image automation, zintegrowane z `taskfile`.

## Features covered

- **GitOps** — pull-based deployment from Git
- **`env_file`** — per-environment cluster config
- **Multi-cluster** — staging, prod
- **Helm Controller** — declarative Helm releases
- **Image Automation** — auto-update on new images

## 🎯 Workflow

```bash
# 1. Wypakowanie projektu
markpact README.md && cd sandbox

# 2. Bootstrap Flux
taskfile --env staging run bootstrap

# 3. Status
taskfile --env staging run status

# 4. Reconcile (force sync)
taskfile --env staging run reconcile

# 5. Logs
taskfile --env staging run logs

# 6. Uninstall
taskfile --env staging run uninstall
```

## 🔧 Dostępne komendy

| Komenda | Opis |
|---------|------|
| `taskfile run bootstrap` | Bootstrap FluxCD in cluster |
| `taskfile run status` | Show Flux components status |
| `taskfile run reconcile` | Force reconciliation |
| `taskfile run suspend` | Suspend reconciliation |
| `taskfile run resume` | Resume reconciliation |
| `taskfile run logs` | View Flux controller logs |
| `taskfile run sources` | List GitRepository sources |
| `taskfile run kustomizations` | List Kustomizations |
| `taskfile run helmreleases` | List HelmReleases |
| `taskfile run events` | Show Flux events |
| `taskfile run export` | Export Flux resources |
| `taskfile run uninstall` | Uninstall FluxCD |
| `taskfile run clean` | Remove local manifests |

---

## Pliki projektu (markpact)

### Taskfile.yml — konfiguracja tasków

```markpact:file path=Taskfile.yml
version: "1"
name: fluxcd-gitops
description: "FluxCD GitOps: pull-based deployment from Git with Helm + Kustomize"

variables:
  FLUX_NS: flux-system
  GIT_REPO: https://github.com/myorg/fleet-infra.git
  GIT_BRANCH: main
  GITHUB_USER: myorg
  GITHUB_REPO: fleet-infra

environments:
  staging:
    env_file: .env.staging
    variables:
      KUBECONFIG: ~/.kube/config-staging
      CONTEXT: staging-cluster
      CLUSTER_PATH: clusters/staging

  prod:
    env_file: .env.prod
    variables:
      KUBECONFIG: ~/.kube/config-prod
      CONTEXT: prod-cluster
      CLUSTER_PATH: clusters/prod

tasks:

  bootstrap:
    desc: Bootstrap FluxCD in Kubernetes cluster
    cmds:
      - kubectl config use-context ${CONTEXT}
      - >-
        flux bootstrap github
        --owner=${GITHUB_USER}
        --repository=${GITHUB_REPO}
        --branch=${GIT_BRANCH}
        --path=${CLUSTER_PATH}
        --personal

  status:
    desc: Show Flux components and reconciliation status
    cmds:
      - kubectl config use-context ${CONTEXT}
      - flux check
      - flux get all -A

  reconcile:
    desc: Force reconciliation of all sources
    cmds:
      - kubectl config use-context ${CONTEXT}
      - flux reconcile source git flux-system
      - flux reconcile kustomization flux-system

  suspend:
    desc: Suspend reconciliation
    cmds:
      - kubectl config use-context ${CONTEXT}
      - flux suspend kustomization flux-system

  resume:
    desc: Resume reconciliation
    cmds:
      - kubectl config use-context ${CONTEXT}
      - flux resume kustomization flux-system

  logs:
    desc: View Flux controller logs
    cmds:
      - kubectl config use-context ${CONTEXT}
      - flux logs --all-namespaces --tail 50

  sources:
    desc: List GitRepository and HelmRepository sources
    cmds:
      - kubectl config use-context ${CONTEXT}
      - flux get sources all -A

  kustomizations:
    desc: List Kustomizations and their status
    cmds:
      - kubectl config use-context ${CONTEXT}
      - flux get kustomizations -A

  helmreleases:
    desc: List HelmReleases and their status
    cmds:
      - kubectl config use-context ${CONTEXT}
      - flux get helmreleases -A

  events:
    desc: Show Flux-related events
    cmds:
      - kubectl config use-context ${CONTEXT}
      - flux events --for Kustomization/flux-system

  export:
    desc: Export Flux resources to YAML
    cmds:
      - kubectl config use-context ${CONTEXT}
      - mkdir -p export
      - flux export source git --all > export/git-sources.yaml
      - flux export kustomization --all > export/kustomizations.yaml
      - flux export helmrelease --all -A > export/helmreleases.yaml

  uninstall:
    desc: Uninstall FluxCD from cluster
    cmds:
      - kubectl config use-context ${CONTEXT}
      - flux uninstall --silent

  clean:
    desc: Remove local export files
    cmds:
      - rm -rf export/
```

### clusters/staging/kustomization.yaml — Flux cluster config

```markpact:file path=clusters/staging/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - sources.yaml
  - apps.yaml
```

### clusters/staging/sources.yaml — Git and Helm sources

```markpact:file path=clusters/staging/sources.yaml
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: my-app
  namespace: flux-system
spec:
  interval: 1m
  url: https://github.com/myorg/my-app.git
  ref:
    branch: main
---
apiVersion: source.toolkit.fluxcd.io/v1beta2
kind: HelmRepository
metadata:
  name: bitnami
  namespace: flux-system
spec:
  interval: 30m
  url: https://charts.bitnami.com/bitnami
```

### clusters/staging/apps.yaml — Application definitions

```markpact:file path=clusters/staging/apps.yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: my-app
  namespace: flux-system
spec:
  interval: 5m
  path: ./deploy/staging
  prune: true
  sourceRef:
    kind: GitRepository
    name: my-app
  healthChecks:
    - apiVersion: apps/v1
      kind: Deployment
      name: my-app
      namespace: staging
---
apiVersion: helm.toolkit.fluxcd.io/v2beta2
kind: HelmRelease
metadata:
  name: redis
  namespace: staging
spec:
  interval: 5m
  chart:
    spec:
      chart: redis
      version: "18.x"
      sourceRef:
        kind: HelmRepository
        name: bitnami
        namespace: flux-system
  values:
    architecture: standalone
    auth:
      enabled: false
```

### .env.staging

```markpact:file path=.env.staging
KUBECONFIG=~/.kube/config-staging
GITHUB_TOKEN=ghp_your_token_here
```

---

## 📚 Dokumentacja

- [FluxCD Docs](https://fluxcd.io/flux/)
- [FluxCD Get Started](https://fluxcd.io/flux/get-started/)
- [Flux Components](https://fluxcd.io/flux/components/)

**Licencja:** MIT
