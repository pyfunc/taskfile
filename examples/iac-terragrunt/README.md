# IaC Terragrunt — DRY Terraform Wrapper + Markpact

**Cały projekt Terragrunt w jednym pliku README.md — wypakuj i uruchom przez Taskfile.**

## 📋 Co to jest?

Terragrunt — wrapper na Terraform/OpenTofu eliminujący powtórzenia (DRY).
Hierarchiczna konfiguracja, dependency management między modułami,
multi-account/multi-region, zintegrowane z `taskfile`.

## Features covered

- **`dir`** — tasks run inside `live/` directory
- **`env_file`** — per-environment AWS account config
- **DRY config** — shared terragrunt.hcl
- **Dependencies** — cross-module dependencies
- **Multi-account** — dev, staging, prod AWS accounts
- **`run-all`** — apply all modules in dependency order

## 🎯 Workflow

```bash
# 1. Wypakowanie projektu
markpact README.md && cd sandbox

# 2. Plan single module
taskfile --env dev run plan --var MODULE=vpc

# 3. Apply single module
taskfile --env dev run apply --var MODULE=vpc

# 4. Plan-all (all modules in dependency order)
taskfile --env dev run plan-all

# 5. Apply-all
taskfile --env dev run apply-all

# 6. Graph
taskfile --env dev run graph

# 7. Destroy
taskfile --env dev run destroy --var MODULE=vpc
```

## 🔧 Dostępne komendy

| Komenda | Opis |
|---------|------|
| `taskfile run plan` | Plan single module |
| `taskfile run apply` | Apply single module |
| `taskfile run destroy` | Destroy single module |
| `taskfile run plan-all` | Plan all modules (dependency order) |
| `taskfile run apply-all` | Apply all modules |
| `taskfile run destroy-all` | Destroy all modules (reverse order) |
| `taskfile run output` | Show module outputs |
| `taskfile run graph` | Show dependency graph |
| `taskfile run validate-all` | Validate all modules |
| `taskfile run hclfmt` | Format HCL files |
| `taskfile run render-json` | Render final JSON config |
| `taskfile run clean` | Remove .terragrunt-cache |

---

## Pliki projektu (markpact)

### Taskfile.yml — konfiguracja tasków

```markpact:file path=Taskfile.yml
version: "1"
name: terragrunt-infra
description: "Terragrunt: DRY Terraform wrapper with multi-account/multi-region"

variables:
  LIVE_DIR: live
  MODULE: vpc

environments:
  dev:
    env_file: .env.dev
    variables:
      ENV_DIR: ${LIVE_DIR}/dev
      AWS_PROFILE: dev
      AWS_REGION: eu-west-1

  staging:
    env_file: .env.staging
    variables:
      ENV_DIR: ${LIVE_DIR}/staging
      AWS_PROFILE: staging
      AWS_REGION: eu-west-1

  prod:
    env_file: .env.prod
    variables:
      ENV_DIR: ${LIVE_DIR}/prod
      AWS_PROFILE: prod
      AWS_REGION: eu-west-1

environment_groups:
  all-prod:
    members: [prod]
    strategy: rolling
    max_parallel: 1

tasks:

  plan:
    desc: Plan single module (use --var MODULE=vpc)
    dir: ${ENV_DIR}/${MODULE}
    cmds:
      - terragrunt plan

  apply:
    desc: Apply single module
    dir: ${ENV_DIR}/${MODULE}
    cmds:
      - terragrunt apply -auto-approve

  destroy:
    desc: Destroy single module
    dir: ${ENV_DIR}/${MODULE}
    cmds:
      - terragrunt destroy -auto-approve

  plan-all:
    desc: Plan all modules in dependency order
    dir: ${ENV_DIR}
    cmds:
      - terragrunt run-all plan

  apply-all:
    desc: Apply all modules in dependency order
    dir: ${ENV_DIR}
    cmds:
      - terragrunt run-all apply --terragrunt-non-interactive

  destroy-all:
    desc: Destroy all modules (reverse dependency order)
    dir: ${ENV_DIR}
    cmds:
      - terragrunt run-all destroy --terragrunt-non-interactive

  output:
    desc: Show module outputs
    dir: ${ENV_DIR}/${MODULE}
    cmds:
      - terragrunt output -json

  graph:
    desc: Show dependency graph between modules
    dir: ${ENV_DIR}
    cmds:
      - terragrunt graph-dependencies

  validate-all:
    desc: Validate all modules
    dir: ${ENV_DIR}
    cmds:
      - terragrunt run-all validate

  hclfmt:
    desc: Format all HCL files
    cmds:
      - terragrunt hclfmt

  render-json:
    desc: Render final terragrunt JSON config (debug)
    dir: ${ENV_DIR}/${MODULE}
    cmds:
      - terragrunt render-json

  clean:
    desc: Remove all .terragrunt-cache directories
    cmds:
      - find ${LIVE_DIR} -type d -name ".terragrunt-cache" -exec rm -rf {} + 2>/dev/null || true
      - find ${LIVE_DIR} -name "*.tfplan" -delete 2>/dev/null || true
```

### live/terragrunt.hcl — Root config (DRY)

```markpact:file path=live/terragrunt.hcl
# Root terragrunt.hcl — shared configuration

locals {
  account_vars = read_terragrunt_config(find_in_parent_folders("account.hcl"))
  region_vars  = read_terragrunt_config(find_in_parent_folders("region.hcl"))

  account_id = local.account_vars.locals.account_id
  aws_region = local.region_vars.locals.aws_region
}

generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
provider "aws" {
  region = "${local.aws_region}"
  allowed_account_ids = ["${local.account_id}"]
}
EOF
}

remote_state {
  backend = "s3"
  config = {
    bucket         = "myorg-terraform-state"
    key            = "${path_relative_to_include()}/terraform.tfstate"
    region         = "eu-west-1"
    encrypt        = true
    dynamodb_table = "terraform-locks"
  }
  generate = {
    path      = "backend.tf"
    if_exists = "overwrite_terragrunt"
  }
}

inputs = {
  environment = basename(get_terragrunt_dir())
  aws_region  = local.aws_region
}
```

### live/dev/account.hcl

```markpact:file path=live/dev/account.hcl
locals {
  account_id   = "111111111111"
  account_name = "dev"
}
```

### live/dev/region.hcl

```markpact:file path=live/dev/region.hcl
locals {
  aws_region = "eu-west-1"
}
```

### live/dev/vpc/terragrunt.hcl — VPC module

```markpact:file path=live/dev/vpc/terragrunt.hcl
terraform {
  source = "../../../modules//vpc"
}

include "root" {
  path = find_in_parent_folders()
}

inputs = {
  vpc_cidr    = "10.0.0.0/16"
  vpc_name    = "dev-vpc"
  environment = "dev"
}
```

### modules/vpc/main.tf — Reusable VPC module

```markpact:file path=modules/vpc/main.tf
variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}

variable "vpc_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "aws_region" {
  type    = string
  default = "eu-west-1"
}

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true

  tags = {
    Name        = var.vpc_name
    Environment = var.environment
    ManagedBy   = "terragrunt"
  }
}

output "vpc_id" {
  value = aws_vpc.main.id
}

output "vpc_cidr" {
  value = aws_vpc.main.cidr_block
}
```

### .env.dev

```markpact:file path=.env.dev
AWS_PROFILE=dev
AWS_DEFAULT_REGION=eu-west-1
```

---

## 📚 Dokumentacja

- [Terragrunt Docs](https://terragrunt.gruntwork.io/docs/)
- [Terragrunt Quick Start](https://terragrunt.gruntwork.io/docs/getting-started/quick-start/)
- [Terragrunt Examples](https://github.com/gruntwork-io/terragrunt-infrastructure-live-example)

**Licencja:** MIT
