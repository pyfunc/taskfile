# IaC Helm — Kubernetes Package Manager + Markpact

**Cały projekt Helm w jednym pliku README.md — wypakuj i uruchom przez Taskfile.**

## 📋 Co to jest?

Helm — menedżer pakietów dla Kubernetes. Chart development, testing,
packaging, publishing — multi-environment, zintegrowane z `taskfile`.

## Features covered

- **`dir`** — tasks run inside `charts/` directory
- **`env_file`** — per-environment values files
- **`deps`** — lint + test before install
- **Chart testing** — helm-unittest, ct lint
- **OCI registry** — push charts to OCI registry

## 🎯 Workflow

```bash
# 1. Wypakowanie projektu
markpact README.md && cd sandbox

# 2. Lint
taskfile run lint

# 3. Template rendering
taskfile --env dev run template

# 4. Install/upgrade
taskfile --env dev run install
taskfile --env staging run install
taskfile --env prod run install

# 5. Diff before upgrade
taskfile --env prod run diff

# 6. Rollback
taskfile --env prod run rollback

# 7. Package & publish
taskfile run package
taskfile run push
```

## 🔧 Dostępne komendy

| Komenda | Opis |
|---------|------|
| `taskfile run lint` | Lint Helm chart |
| `taskfile run template` | Render templates locally |
| `taskfile run install` | Install or upgrade release |
| `taskfile run uninstall` | Uninstall release |
| `taskfile run diff` | Preview changes (helm-diff) |
| `taskfile run rollback` | Rollback to previous revision |
| `taskfile run history` | Show release history |
| `taskfile run status` | Show release status |
| `taskfile run test` | Run chart tests |
| `taskfile run package` | Package chart to .tgz |
| `taskfile run push` | Push chart to OCI registry |
| `taskfile run dep-update` | Update chart dependencies |
| `taskfile run clean` | Remove packaged charts |

---

## Pliki projektu (markpact)

### Taskfile.yml — konfiguracja tasków

```markpact:file path=Taskfile.yml
version: "1"
name: helm-charts
description: "Helm: chart development, testing, packaging, multi-env deployment"

variables:
  CHART_DIR: charts/my-app
  CHART_NAME: my-app
  RELEASE_NAME: my-app
  NAMESPACE: default
  REGISTRY: ghcr.io/myorg/charts
  REPLICAS: "2"

environments:
  dev:
    env_file: .env.dev
    variables:
      KUBECONFIG: ~/.kube/config
      CONTEXT: minikube
      NAMESPACE: dev
      VALUES_FILE: values-dev.yaml
      REPLICAS: "1"

  staging:
    env_file: .env.staging
    variables:
      KUBECONFIG: ~/.kube/config-staging
      CONTEXT: staging-cluster
      NAMESPACE: staging
      VALUES_FILE: values-staging.yaml
      REPLICAS: "2"

  prod:
    env_file: .env.prod
    variables:
      KUBECONFIG: ~/.kube/config-prod
      CONTEXT: prod-cluster
      NAMESPACE: production
      VALUES_FILE: values-prod.yaml
      REPLICAS: "5"

tasks:

  lint:
    desc: Lint Helm chart
    cmds:
      - helm lint ${CHART_DIR}
      - helm template ${RELEASE_NAME} ${CHART_DIR} | kubectl apply --dry-run=client -f -

  template:
    desc: Render templates with environment values
    cmds:
      - kubectl config use-context ${CONTEXT}
      - helm template ${RELEASE_NAME} ${CHART_DIR} --namespace ${NAMESPACE} -f ${CHART_DIR}/${VALUES_FILE}

  install:
    desc: Install or upgrade Helm release
    deps: [lint]
    cmds:
      - kubectl config use-context ${CONTEXT}
      - >-
        helm upgrade --install ${RELEASE_NAME} ${CHART_DIR}
        --namespace ${NAMESPACE} --create-namespace
        -f ${CHART_DIR}/${VALUES_FILE}
        --set replicaCount=${REPLICAS}
        --wait --timeout 5m

  uninstall:
    desc: Uninstall Helm release
    cmds:
      - kubectl config use-context ${CONTEXT}
      - helm uninstall ${RELEASE_NAME} --namespace ${NAMESPACE}

  diff:
    desc: Preview changes before upgrade (requires helm-diff plugin)
    cmds:
      - kubectl config use-context ${CONTEXT}
      - >-
        helm diff upgrade ${RELEASE_NAME} ${CHART_DIR}
        --namespace ${NAMESPACE}
        -f ${CHART_DIR}/${VALUES_FILE}
        --set replicaCount=${REPLICAS}

  rollback:
    desc: Rollback to previous revision
    cmds:
      - kubectl config use-context ${CONTEXT}
      - helm rollback ${RELEASE_NAME} --namespace ${NAMESPACE} --wait

  history:
    desc: Show release history
    cmds:
      - kubectl config use-context ${CONTEXT}
      - helm history ${RELEASE_NAME} --namespace ${NAMESPACE}

  status:
    desc: Show release status and resources
    cmds:
      - kubectl config use-context ${CONTEXT}
      - helm status ${RELEASE_NAME} --namespace ${NAMESPACE}
      - kubectl -n ${NAMESPACE} get all -l app.kubernetes.io/name=${CHART_NAME}

  test:
    desc: Run Helm chart tests
    cmds:
      - kubectl config use-context ${CONTEXT}
      - helm test ${RELEASE_NAME} --namespace ${NAMESPACE}

  package:
    desc: Package chart to .tgz archive
    cmds:
      - helm package ${CHART_DIR} --destination dist/

  push:
    desc: Push chart to OCI registry
    deps: [package]
    cmds:
      - helm push dist/${CHART_NAME}-*.tgz oci://${REGISTRY}

  dep-update:
    desc: Update chart dependencies
    cmds:
      - helm dependency update ${CHART_DIR}

  clean:
    desc: Remove packaged charts and caches
    cmds:
      - rm -rf dist/
      - rm -f ${CHART_DIR}/charts/*.tgz
```

### charts/my-app/Chart.yaml

```markpact:file path=charts/my-app/Chart.yaml
apiVersion: v2
name: my-app
description: A Helm chart for my application
type: application
version: 0.1.0
appVersion: "1.0.0"

maintainers:
  - name: Your Name
    email: you@example.com

dependencies: []
```

### charts/my-app/values.yaml — default values

```markpact:file path=charts/my-app/values.yaml
replicaCount: 2

image:
  repository: ghcr.io/myorg/my-app
  pullPolicy: IfNotPresent
  tag: "latest"

service:
  type: ClusterIP
  port: 80

ingress:
  enabled: false
  className: nginx
  hosts:
    - host: app.example.com
      paths:
        - path: /
          pathType: Prefix

resources:
  limits:
    cpu: 500m
    memory: 256Mi
  requests:
    cpu: 100m
    memory: 128Mi

autoscaling:
  enabled: false
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 80
```

### charts/my-app/values-dev.yaml

```markpact:file path=charts/my-app/values-dev.yaml
replicaCount: 1

image:
  tag: "dev"
  pullPolicy: Always

resources:
  limits:
    cpu: 250m
    memory: 128Mi
  requests:
    cpu: 50m
    memory: 64Mi
```

### charts/my-app/values-prod.yaml

```markpact:file path=charts/my-app/values-prod.yaml
replicaCount: 5

image:
  tag: "latest"
  pullPolicy: IfNotPresent

ingress:
  enabled: true
  className: nginx
  hosts:
    - host: app.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: app-tls
      hosts:
        - app.example.com

autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 20
  targetCPUUtilizationPercentage: 70

resources:
  limits:
    cpu: "1"
    memory: 512Mi
  requests:
    cpu: 250m
    memory: 256Mi
```

### charts/my-app/templates/deployment.yaml

```markpact:file path=charts/my-app/templates/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "my-app.fullname" . }}
  labels:
    {{- include "my-app.labels" . | nindent 4 }}
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      {{- include "my-app.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      labels:
        {{- include "my-app.selectorLabels" . | nindent 8 }}
    spec:
      containers:
        - name: {{ .Chart.Name }}
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          ports:
            - name: http
              containerPort: 8000
              protocol: TCP
          livenessProbe:
            httpGet:
              path: /health
              port: http
          readinessProbe:
            httpGet:
              path: /health
              port: http
          resources:
            {{- toYaml .Values.resources | nindent 12 }}
```

### .env.dev

```markpact:file path=.env.dev
KUBECONFIG=~/.kube/config
```

---

## 📚 Dokumentacja

- [Helm Docs](https://helm.sh/docs/)
- [Helm Best Practices](https://helm.sh/docs/chart_best_practices/)
- [Artifact Hub](https://artifacthub.io/)

**Licencja:** MIT
