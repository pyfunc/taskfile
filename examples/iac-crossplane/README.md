# IaC Crossplane — Kubernetes-Native Cloud Infrastructure + Markpact

**Cały projekt Crossplane w jednym pliku README.md — wypakuj i uruchom przez Taskfile.**

## 📋 Co to jest?

Crossplane — zarządzaj infrastrukturą chmurową jako zasobami Kubernetes.
Multi-cloud (AWS/GCP/Azure), Compositions, Claims, zintegrowane z `taskfile`.

## Features covered

- **Kubernetes-native** — kubectl apply for infrastructure
- **`env_file`** — per-environment cloud provider config
- **Multi-cloud** — AWS, GCP, Azure providers
- **Compositions** — reusable infrastructure abstractions
- **XRDs** — custom resource definitions

## 🎯 Workflow

```bash
# 1. Wypakowanie projektu
markpact README.md && cd sandbox

# 2. Instalacja Crossplane
taskfile run install

# 3. Konfiguracja providera
taskfile --env aws run configure-provider

# 4. Deploy infrastruktury
taskfile --env aws run apply

# 5. Status
taskfile --env aws run status

# 6. Clean
taskfile --env aws run delete
```

## 🔧 Dostępne komendy

| Komenda | Opis |
|---------|------|
| `taskfile run install` | Install Crossplane in K8s cluster |
| `taskfile run configure-provider` | Configure cloud provider |
| `taskfile run apply` | Apply infrastructure manifests |
| `taskfile run delete` | Delete infrastructure |
| `taskfile run status` | Show managed resources status |
| `taskfile run compositions` | List available compositions |
| `taskfile run claims` | List active claims |
| `taskfile run providers` | List installed providers |
| `taskfile run clean` | Uninstall Crossplane |

---

## Pliki projektu (markpact)

### Taskfile.yml — konfiguracja tasków

```markpact:file path=Taskfile.yml
version: "1"
name: crossplane-infra
description: "Crossplane: Kubernetes-native cloud infrastructure management"

variables:
  MANIFESTS_DIR: manifests
  CROSSPLANE_NS: crossplane-system

environments:
  aws:
    env_file: .env.aws
    variables:
      PROVIDER: provider-aws
      PROVIDER_VERSION: v0.47.0
      PROVIDER_CONFIG: aws-provider-config.yaml
      INFRA_DIR: ${MANIFESTS_DIR}/aws

  gcp:
    env_file: .env.gcp
    variables:
      PROVIDER: provider-gcp
      PROVIDER_VERSION: v0.40.0
      PROVIDER_CONFIG: gcp-provider-config.yaml
      INFRA_DIR: ${MANIFESTS_DIR}/gcp

  azure:
    env_file: .env.azure
    variables:
      PROVIDER: provider-azure
      PROVIDER_VERSION: v0.42.0
      PROVIDER_CONFIG: azure-provider-config.yaml
      INFRA_DIR: ${MANIFESTS_DIR}/azure

tasks:

  install:
    desc: Install Crossplane in Kubernetes cluster
    cmds:
      - helm repo add crossplane-stable https://charts.crossplane.io/stable
      - helm repo update
      - >-
        helm upgrade --install crossplane crossplane-stable/crossplane
        --namespace ${CROSSPLANE_NS} --create-namespace
        --wait --timeout 5m

  configure-provider:
    desc: Install and configure cloud provider
    cmds:
      - kubectl apply -f ${MANIFESTS_DIR}/providers/${PROVIDER}.yaml
      - kubectl wait --for=condition=healthy provider/${PROVIDER} --timeout=300s
      - kubectl apply -f ${MANIFESTS_DIR}/providers/${PROVIDER_CONFIG}

  apply:
    desc: Apply infrastructure manifests
    cmds:
      - kubectl apply -f ${INFRA_DIR}/

  delete:
    desc: Delete infrastructure resources
    cmds:
      - kubectl delete -f ${INFRA_DIR}/

  status:
    desc: Show managed resources status
    cmds:
      - kubectl get managed -o wide
      - kubectl get claim -A -o wide

  compositions:
    desc: List available compositions
    cmds:
      - kubectl get compositions
      - kubectl get xrd

  claims:
    desc: List active claims
    cmds:
      - kubectl get claim -A

  providers:
    desc: List installed providers and their status
    cmds:
      - kubectl get providers
      - kubectl get providerconfigs

  clean:
    desc: Uninstall Crossplane
    cmds:
      - helm uninstall crossplane -n ${CROSSPLANE_NS}
      - kubectl delete namespace ${CROSSPLANE_NS}
```

### manifests/providers/provider-aws.yaml

```markpact:file path=manifests/providers/provider-aws.yaml
apiVersion: pkg.crossplane.io/v1
kind: Provider
metadata:
  name: provider-aws
spec:
  package: xpkg.upbound.io/upbound/provider-aws-ec2:v0.47.0
  runtimeConfigRef:
    name: default
```

### manifests/aws/vpc.yaml — Example AWS VPC

```markpact:file path=manifests/aws/vpc.yaml
apiVersion: ec2.aws.upbound.io/v1beta1
kind: VPC
metadata:
  name: my-vpc
spec:
  forProvider:
    region: eu-west-1
    cidrBlock: 10.0.0.0/16
    enableDnsHostnames: true
    enableDnsSupport: true
    tags:
      Name: my-vpc
      ManagedBy: crossplane-taskfile
  providerConfigRef:
    name: aws-provider
```

### .env.aws

```markpact:file path=.env.aws
AWS_PROFILE=crossplane
AWS_DEFAULT_REGION=eu-west-1
```

---

## 📚 Dokumentacja

- [Crossplane Docs](https://docs.crossplane.io/)
- [Upbound Marketplace](https://marketplace.upbound.io/)

**Licencja:** MIT
