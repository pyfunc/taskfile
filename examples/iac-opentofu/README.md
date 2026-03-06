# IaC OpenTofu — Open-Source Terraform Fork + Markpact

**Cały projekt OpenTofu w jednym pliku README.md — wypakuj i uruchom przez Taskfile.**

## 📋 Co to jest?

OpenTofu — open-source fork Terraform (Linux Foundation). Pełna kompatybilność
z modułami i providerami Terraform. Multi-environment, state encryption, zintegrowane z `taskfile`.

## Features covered

- **`dir`** — tasks run inside `tofu/` directory
- **`env_file`** — per-environment credentials
- **`condition`** — tofu vs terraform fallback
- **`environment_groups`** — `all-prod` for rolling updates
- **State encryption** — built-in OpenTofu feature
- **`deps` + `parallel`** — validate + lint before plan

## 🎯 Workflow

```bash
# 1. Wypakowanie projektu
markpact README.md && cd sandbox

# 2. Init
taskfile --env dev run init

# 3. Plan + apply
taskfile --env dev run plan
taskfile --env dev run apply

# 4. Rolling prod
taskfile -G all-prod run plan
taskfile -G all-prod run apply

# 5. State encryption
taskfile --env prod run enable-encryption

# 6. Destroy
taskfile --env dev run destroy
```

## 🔧 Dostępne komendy

| Komenda | Opis |
|---------|------|
| `taskfile run init` | Initialize OpenTofu backend |
| `taskfile run plan` | Generate execution plan |
| `taskfile run apply` | Apply infrastructure changes |
| `taskfile run destroy` | Destroy all resources |
| `taskfile run output` | Show outputs |
| `taskfile run state-list` | List resources in state |
| `taskfile run validate` | Validate configuration |
| `taskfile run lint` | Lint with tflint |
| `taskfile run enable-encryption` | Enable state encryption |
| `taskfile run migrate-from-tf` | Migrate from Terraform state |
| `taskfile run clean` | Remove local state files |

---

## Pliki projektu (markpact)

### Taskfile.yml — konfiguracja tasków

```markpact:file path=Taskfile.yml
version: "1"
name: opentofu-infra
description: "OpenTofu IaC: open-source Terraform fork with state encryption"

variables:
  TOFU_DIR: tofu
  STATE_BUCKET: myorg-tofu-state
  PROJECT: my-infra

environments:
  dev:
    env_file: .env.dev
    variables:
      WORKSPACE: dev
      AWS_REGION: eu-west-1
      INSTANCE_TYPE: t3.small
      INSTANCE_COUNT: "1"

  staging:
    env_file: .env.staging
    variables:
      WORKSPACE: staging
      AWS_REGION: eu-west-1
      INSTANCE_TYPE: t3.medium
      INSTANCE_COUNT: "2"

  prod:
    env_file: .env.prod
    variables:
      WORKSPACE: prod
      AWS_REGION: eu-west-1
      INSTANCE_TYPE: t3.large
      INSTANCE_COUNT: "3"

  prod-us:
    env_file: .env.prod-us
    variables:
      WORKSPACE: prod-us
      AWS_REGION: us-east-1
      INSTANCE_TYPE: t3.large
      INSTANCE_COUNT: "3"

environment_groups:
  all-prod:
    members: [prod, prod-us]
    strategy: rolling
    max_parallel: 1

tasks:

  init:
    desc: Initialize OpenTofu backend + providers
    dir: ${TOFU_DIR}
    cmds:
      - >-
        tofu init
        -backend-config="bucket=${STATE_BUCKET}"
        -backend-config="key=${PROJECT}/${WORKSPACE}/terraform.tfstate"
        -backend-config="region=${AWS_REGION}"

  workspace:
    desc: Select or create workspace
    dir: ${TOFU_DIR}
    deps: [init]
    cmds:
      - tofu workspace select ${WORKSPACE} || tofu workspace new ${WORKSPACE}

  validate:
    desc: Validate configuration
    dir: ${TOFU_DIR}
    deps: [workspace]
    cmds:
      - tofu validate
      - tofu fmt -check -recursive

  plan:
    desc: Generate execution plan
    dir: ${TOFU_DIR}
    deps: [workspace]
    cmds:
      - >-
        tofu plan
        -var="region=${AWS_REGION}"
        -var="instance_type=${INSTANCE_TYPE}"
        -var="instance_count=${INSTANCE_COUNT}"
        -out=tfplan

  apply:
    desc: Apply infrastructure changes
    dir: ${TOFU_DIR}
    deps: [plan]
    cmds:
      - tofu apply tfplan

  destroy:
    desc: Destroy all infrastructure
    dir: ${TOFU_DIR}
    deps: [workspace]
    cmds:
      - >-
        tofu destroy
        -var="region=${AWS_REGION}"
        -var="instance_type=${INSTANCE_TYPE}"
        -var="instance_count=${INSTANCE_COUNT}"
        -auto-approve

  output:
    desc: Show outputs
    dir: ${TOFU_DIR}
    cmds:
      - tofu output -json

  state-list:
    desc: List all resources in state
    dir: ${TOFU_DIR}
    cmds:
      - tofu state list

  lint:
    desc: Lint configuration (tflint)
    dir: ${TOFU_DIR}
    condition: "command -v tflint >/dev/null 2>&1"
    cmds:
      - tflint --recursive
    ignore_errors: true

  enable-encryption:
    desc: Enable OpenTofu state encryption
    dir: ${TOFU_DIR}
    cmds:
      - echo "Add encryption block to backend configuration"
      - tofu init -reconfigure

  migrate-from-tf:
    desc: Migrate from Terraform state to OpenTofu
    dir: ${TOFU_DIR}
    cmds:
      - tofu init -migrate-state

  clean:
    desc: Remove local state + plan files
    dir: ${TOFU_DIR}
    cmds:
      - rm -f tfplan terraform.tfstate.backup
      - rm -rf .terraform/
```

### tofu/main.tf — OpenTofu configuration

```markpact:file path=tofu/main.tf
terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {}

  # OpenTofu state encryption (optional)
  # encryption {
  #   method "aes_gcm" "default" {
  #     keys = key_provider.pbkdf2.default
  #   }
  #   state {
  #     method   = method.aes_gcm.default
  #     enforced = true
  #   }
  # }
}

variable "region" {
  type    = string
  default = "eu-west-1"
}

variable "instance_type" {
  type    = string
  default = "t3.small"
}

variable "instance_count" {
  type    = number
  default = 1
}

provider "aws" {
  region = var.region
}

resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true

  tags = {
    Name        = "main-vpc"
    ManagedBy   = "opentofu"
    Environment = terraform.workspace
  }
}

output "vpc_id" {
  value = aws_vpc.main.id
}
```

### .env.dev

```markpact:file path=.env.dev
AWS_PROFILE=dev
AWS_DEFAULT_REGION=eu-west-1
```

---

## 📚 Dokumentacja

- [OpenTofu Docs](https://opentofu.org/docs/)
- [OpenTofu State Encryption](https://opentofu.org/docs/language/state/encryption/)
- [Migration from Terraform](https://opentofu.org/docs/intro/migration/)

**Licencja:** MIT
