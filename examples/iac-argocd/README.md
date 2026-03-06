# IaC ArgoCD — GitOps for Kubernetes + Markpact

**Cały projekt ArgoCD w jednym pliku README.md — wypakuj i uruchom przez Taskfile.**

## 📋 Co to jest?

ArgoCD — GitOps continuous delivery dla Kubernetes. Deklaratywne zarządzanie
aplikacjami, auto-sync, multi-cluster, zintegrowane z `taskfile`.

## Features covered

- **GitOps** — infrastructure defined in Git
- **`env_file`** — per-environment cluster config
- **Multi-cluster** — staging, prod-eu, prod-us
- **Auto-sync** — automatic reconciliation
- **App of Apps** — pattern for managing multiple apps

## 🎯 Workflow

```bash
# 1. Wypakowanie projektu
markpact README.md && cd sandbox

# 2. Instalacja ArgoCD
taskfile run install

# 3. Login
taskfile run login

# 4. Dodanie aplikacji
taskfile --env staging run create-app
taskfile --env prod run create-app

# 5. Sync
taskfile --env staging run sync

# 6. Status
taskfile --env staging run status

# 7. Rollback
taskfile --env staging run rollback
```

## 🔧 Dostępne komendy

| Komenda | Opis |
|---------|------|
| `taskfile run install` | Install ArgoCD in cluster |
| `taskfile run login` | Login to ArgoCD CLI |
| `taskfile run create-app` | Create ArgoCD Application |
| `taskfile run sync` | Sync application (deploy) |
| `taskfile run status` | Show app sync status |
| `taskfile run diff` | Show diff between desired and live |
| `taskfile run rollback` | Rollback to previous revision |
| `taskfile run history` | Show deployment history |
| `taskfile run logs` | View application logs |
| `taskfile run delete-app` | Delete ArgoCD Application |
| `taskfile run port-forward` | Access ArgoCD UI locally |
| `taskfile run clean` | Uninstall ArgoCD |

---

## Pliki projektu (markpact)

### Taskfile.yml — konfiguracja tasków

```markpact:file path=Taskfile.yml
version: "1"
name: argocd-gitops
description: "ArgoCD GitOps: multi-cluster Kubernetes deployment with auto-sync"

variables:
  ARGOCD_NS: argocd
  APP_NAME: my-app
  REPO_URL: https://github.com/myorg/my-app.git
  TARGET_REVISION: HEAD

environments:
  staging:
    env_file: .env.staging
    variables:
      CLUSTER_URL: https://staging-k8s.example.com
      NAMESPACE: staging
      PATH_PREFIX: envs/staging
      AUTO_SYNC: "true"

  prod-eu:
    env_file: .env.prod-eu
    variables:
      CLUSTER_URL: https://prod-eu-k8s.example.com
      NAMESPACE: production
      PATH_PREFIX: envs/prod-eu
      AUTO_SYNC: "false"

  prod-us:
    env_file: .env.prod-us
    variables:
      CLUSTER_URL: https://prod-us-k8s.example.com
      NAMESPACE: production
      PATH_PREFIX: envs/prod-us
      AUTO_SYNC: "false"

environment_groups:
  all-prod:
    members: [prod-eu, prod-us]
    strategy: canary
    canary_count: 1

tasks:

  install:
    desc: Install ArgoCD in Kubernetes cluster
    cmds:
      - kubectl create namespace ${ARGOCD_NS} --dry-run=client -o yaml | kubectl apply -f -
      - kubectl apply -n ${ARGOCD_NS} -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
      - kubectl wait -n ${ARGOCD_NS} deploy/argocd-server --for=condition=available --timeout=300s

  login:
    desc: Login to ArgoCD CLI
    cmds:
      - >-
        argocd login localhost:8080
        --username admin
        --password $(kubectl -n ${ARGOCD_NS} get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d)
        --insecure

  create-app:
    desc: Create ArgoCD Application for environment
    cmds:
      - >-
        argocd app create ${APP_NAME}-${NAMESPACE}
        --repo ${REPO_URL}
        --revision ${TARGET_REVISION}
        --path ${PATH_PREFIX}
        --dest-server ${CLUSTER_URL}
        --dest-namespace ${NAMESPACE}
        --sync-policy automated
        --auto-prune
        --self-heal

  sync:
    desc: Manual sync (deploy latest from Git)
    cmds:
      - argocd app sync ${APP_NAME}-${NAMESPACE} --prune --force

  status:
    desc: Show application sync status
    cmds:
      - argocd app get ${APP_NAME}-${NAMESPACE}

  diff:
    desc: Show diff between desired and live state
    cmds:
      - argocd app diff ${APP_NAME}-${NAMESPACE}
    ignore_errors: true

  rollback:
    desc: Rollback to previous revision
    cmds:
      - argocd app rollback ${APP_NAME}-${NAMESPACE}

  history:
    desc: Show deployment history
    cmds:
      - argocd app history ${APP_NAME}-${NAMESPACE}

  logs:
    desc: View application pod logs
    cmds:
      - argocd app logs ${APP_NAME}-${NAMESPACE} --tail 50

  delete-app:
    desc: Delete ArgoCD Application
    cmds:
      - argocd app delete ${APP_NAME}-${NAMESPACE} --cascade

  port-forward:
    desc: Access ArgoCD UI at https://localhost:8080
    cmds:
      - kubectl port-forward svc/argocd-server -n ${ARGOCD_NS} 8080:443

  clean:
    desc: Uninstall ArgoCD from cluster
    cmds:
      - kubectl delete -n ${ARGOCD_NS} -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
      - kubectl delete namespace ${ARGOCD_NS}
```

### envs/staging/kustomization.yaml — Kustomize overlay

```markpact:file path=envs/staging/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: staging

resources:
  - ../../base

patchesStrategicMerge:
  - replica-patch.yaml

configMapGenerator:
  - name: app-config
    literals:
      - ENV=staging
      - LOG_LEVEL=debug
```

### base/deployment.yaml — Base K8s deployment

```markpact:file path=base/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
  labels:
    app: my-app
spec:
  replicas: 2
  selector:
    matchLabels:
      app: my-app
  template:
    metadata:
      labels:
        app: my-app
    spec:
      containers:
        - name: app
          image: ghcr.io/myorg/my-app:latest
          ports:
            - containerPort: 8000
          env:
            - name: ENV
              valueFrom:
                configMapKeyRef:
                  name: app-config
                  key: ENV
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
```

### base/kustomization.yaml

```markpact:file path=base/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - deployment.yaml
  - service.yaml
```

### base/service.yaml

```markpact:file path=base/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: my-app
spec:
  selector:
    app: my-app
  ports:
    - port: 80
      targetPort: 8000
  type: ClusterIP
```

### .env.staging

```markpact:file path=.env.staging
KUBECONFIG=~/.kube/config-staging
```

---

## 📚 Dokumentacja

- [ArgoCD Docs](https://argo-cd.readthedocs.io/)
- [ArgoCD Best Practices](https://argo-cd.readthedocs.io/en/stable/user-guide/best_practices/)
- [App of Apps Pattern](https://argo-cd.readthedocs.io/en/stable/operator-manual/cluster-bootstrapping/)

**Licencja:** MIT
