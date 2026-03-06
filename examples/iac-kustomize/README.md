# IaC Kustomize — Kubernetes Native Configuration Management + Markpact

**Cały projekt Kustomize w jednym pliku README.md — wypakuj i uruchom przez Taskfile.**

## 📋 Co to jest?

Kustomize — natywne narzędzie Kubernetes do zarządzania konfiguracją.
Overlay-based, bez szablonów — czysty YAML z patchami.
Multi-environment, zintegrowane z `taskfile`.

## Features covered

- **`dir`** — tasks run inside `k8s/` directory
- **`env_file`** — per-environment config
- **Overlays** — dev, staging, prod
- **Strategic merge patches** — environment-specific changes
- **ConfigMap/Secret generators** — automatic hashing

## 🎯 Workflow

```bash
# 1. Wypakowanie projektu
markpact README.md && cd sandbox

# 2. Build (render YAML)
taskfile --env dev run build

# 3. Diff
taskfile --env dev run diff

# 4. Apply
taskfile --env dev run apply
taskfile --env staging run apply
taskfile --env prod run apply

# 5. Status
taskfile --env dev run status

# 6. Delete
taskfile --env dev run delete
```

## 🔧 Dostępne komendy

| Komenda | Opis |
|---------|------|
| `taskfile run build` | Render kustomized YAML |
| `taskfile run apply` | Apply to cluster |
| `taskfile run delete` | Delete resources |
| `taskfile run diff` | Diff against live cluster |
| `taskfile run status` | Show deployment status |
| `taskfile run validate` | Dry-run validation |
| `taskfile run edit-image` | Update image tag |
| `taskfile run logs` | View pod logs |
| `taskfile run restart` | Rolling restart |
| `taskfile run clean` | Remove rendered YAML |

---

## Pliki projektu (markpact)

### Taskfile.yml — konfiguracja tasków

```markpact:file path=Taskfile.yml
version: "1"
name: kustomize-app
description: "Kustomize: Kubernetes native configuration management with overlays"

variables:
  K8S_DIR: k8s
  APP_NAME: my-app
  IMAGE: ghcr.io/myorg/my-app
  TAG: latest

environments:
  dev:
    env_file: .env.dev
    variables:
      KUBECONFIG: ~/.kube/config
      CONTEXT: minikube
      OVERLAY: overlays/dev
      NAMESPACE: dev

  staging:
    env_file: .env.staging
    variables:
      KUBECONFIG: ~/.kube/config-staging
      CONTEXT: staging-cluster
      OVERLAY: overlays/staging
      NAMESPACE: staging

  prod:
    env_file: .env.prod
    variables:
      KUBECONFIG: ~/.kube/config-prod
      CONTEXT: prod-cluster
      OVERLAY: overlays/prod
      NAMESPACE: production

tasks:

  build:
    desc: Render kustomized YAML
    dir: ${K8S_DIR}
    cmds:
      - kubectl kustomize ${OVERLAY}

  apply:
    desc: Apply kustomized manifests to cluster
    dir: ${K8S_DIR}
    cmds:
      - kubectl config use-context ${CONTEXT}
      - kubectl apply -k ${OVERLAY}

  delete:
    desc: Delete kustomized resources
    dir: ${K8S_DIR}
    cmds:
      - kubectl config use-context ${CONTEXT}
      - kubectl delete -k ${OVERLAY}

  diff:
    desc: Diff rendered manifests against live cluster
    dir: ${K8S_DIR}
    cmds:
      - kubectl config use-context ${CONTEXT}
      - kubectl diff -k ${OVERLAY}
    ignore_errors: true

  status:
    desc: Show deployment status
    dir: ${K8S_DIR}
    cmds:
      - kubectl config use-context ${CONTEXT}
      - kubectl -n ${NAMESPACE} get all -l app=${APP_NAME}

  validate:
    desc: Dry-run validation
    dir: ${K8S_DIR}
    cmds:
      - kubectl config use-context ${CONTEXT}
      - kubectl apply -k ${OVERLAY} --dry-run=client

  edit-image:
    desc: Update image tag (use --var TAG=v1.0.0)
    dir: ${K8S_DIR}/${OVERLAY}
    cmds:
      - kustomize edit set image ${IMAGE}=${IMAGE}:${TAG}

  logs:
    desc: View pod logs
    cmds:
      - kubectl config use-context ${CONTEXT}
      - kubectl -n ${NAMESPACE} logs -l app=${APP_NAME} --tail=50 -f

  restart:
    desc: Rolling restart deployment
    cmds:
      - kubectl config use-context ${CONTEXT}
      - kubectl -n ${NAMESPACE} rollout restart deploy/${APP_NAME}
      - kubectl -n ${NAMESPACE} rollout status deploy/${APP_NAME}

  clean:
    desc: Remove rendered YAML files
    cmds:
      - rm -f rendered-*.yaml
```

### k8s/base/kustomization.yaml

```markpact:file path=k8s/base/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

commonLabels:
  app: my-app

resources:
  - deployment.yaml
  - service.yaml

configMapGenerator:
  - name: app-config
    literals:
      - APP_NAME=my-app
      - LOG_LEVEL=info
```

### k8s/base/deployment.yaml

```markpact:file path=k8s/base/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
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
          envFrom:
            - configMapRef:
                name: app-config
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 256Mi
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
```

### k8s/base/service.yaml

```markpact:file path=k8s/base/service.yaml
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

### k8s/overlays/dev/kustomization.yaml

```markpact:file path=k8s/overlays/dev/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: dev

resources:
  - ../../base

replicas:
  - name: my-app
    count: 1

images:
  - name: ghcr.io/myorg/my-app
    newTag: dev

configMapGenerator:
  - name: app-config
    behavior: merge
    literals:
      - LOG_LEVEL=debug
      - ENV=dev
```

### k8s/overlays/prod/kustomization.yaml

```markpact:file path=k8s/overlays/prod/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: production

resources:
  - ../../base
  - ingress.yaml

replicas:
  - name: my-app
    count: 5

images:
  - name: ghcr.io/myorg/my-app
    newTag: latest

configMapGenerator:
  - name: app-config
    behavior: merge
    literals:
      - LOG_LEVEL=warn
      - ENV=production

patches:
  - target:
      kind: Deployment
      name: my-app
    patch: |-
      - op: replace
        path: /spec/template/spec/containers/0/resources/limits/cpu
        value: "2"
      - op: replace
        path: /spec/template/spec/containers/0/resources/limits/memory
        value: 1Gi
```

### k8s/overlays/prod/ingress.yaml

```markpact:file path=k8s/overlays/prod/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-app
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - app.example.com
      secretName: app-tls
  rules:
    - host: app.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: my-app
                port:
                  number: 80
```

### .env.dev

```markpact:file path=.env.dev
KUBECONFIG=~/.kube/config
```

---

## 📚 Dokumentacja

- [Kustomize Docs](https://kustomize.io/)
- [Kustomize Reference](https://kubectl.docs.kubernetes.io/references/kustomize/)
- [Kustomize Examples](https://github.com/kubernetes-sigs/kustomize/tree/master/examples)

**Licencja:** MIT
