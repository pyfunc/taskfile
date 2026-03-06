# IaC Pulumi — Infrastructure as Code with Programming Languages + Markpact

**Cały projekt Pulumi w jednym pliku README.md — wypakuj i uruchom przez Taskfile.**

## 📋 Co to jest?

Infrastructure as Code z Pulumi — używaj Pythona/TypeScript/Go zamiast YAML/HCL.
Multi-environment (dev/staging/prod), preview/up/destroy z integracją taskfile.

## Features covered

- **`dir`** — tasks run inside `infra/` directory
- **`env_file`** — per-environment cloud credentials
- **`condition`** — cost estimation only if pulumi is installed
- **`environment_groups`** — `all-prod` for rolling infra updates
- **`deps`** — preview before up, lint before preview

## 🎯 Workflow

```bash
# 1. Wypakowanie projektu
markpact README.md && cd sandbox

# 2. Inicjalizacja
taskfile --env dev run init

# 3. Preview zmian
taskfile --env dev run preview

# 4. Deploy
taskfile --env dev run up
taskfile --env staging run up
taskfile --env prod run up

# 5. Status
taskfile --env prod run stack-output

# 6. Destroy dev
taskfile --env dev run destroy
```

## 🔧 Dostępne komendy

| Komenda | Opis |
|---------|------|
| `taskfile run init` | Initialize Pulumi project + install deps |
| `taskfile run preview` | Preview infrastructure changes |
| `taskfile run up` | Deploy infrastructure |
| `taskfile run destroy` | Destroy all resources |
| `taskfile run stack-output` | Show stack outputs |
| `taskfile run refresh` | Refresh state from cloud |
| `taskfile run lint` | Lint Python/TS code |
| `taskfile run test` | Run unit tests |
| `taskfile run export` | Export stack state |
| `taskfile run import` | Import existing resources |
| `taskfile run clean` | Remove local state files |

---

## Pliki projektu (markpact)

### Taskfile.yml — konfiguracja tasków

```markpact:file path=Taskfile.yml
version: "1"
name: pulumi-infra
description: "Pulumi IaC: multi-env infrastructure with Python/TypeScript"

variables:
  INFRA_DIR: infra
  PULUMI_ORG: myorg
  PROJECT: my-infra

environments:
  dev:
    env_file: .env.dev
    variables:
      PULUMI_STACK: ${PULUMI_ORG}/${PROJECT}/dev
      AWS_REGION: eu-west-1
      INSTANCE_TYPE: t3.small
      INSTANCE_COUNT: "1"

  staging:
    env_file: .env.staging
    variables:
      PULUMI_STACK: ${PULUMI_ORG}/${PROJECT}/staging
      AWS_REGION: eu-west-1
      INSTANCE_TYPE: t3.medium
      INSTANCE_COUNT: "2"

  prod:
    env_file: .env.prod
    variables:
      PULUMI_STACK: ${PULUMI_ORG}/${PROJECT}/prod
      AWS_REGION: eu-west-1
      INSTANCE_TYPE: t3.large
      INSTANCE_COUNT: "3"

environment_groups:
  all-prod:
    members: [prod]
    strategy: rolling
    max_parallel: 1

tasks:

  init:
    desc: Initialize Pulumi project and install dependencies
    dir: ${INFRA_DIR}
    cmds:
      - pulumi stack select ${PULUMI_STACK} --create
      - pip install -r requirements.txt

  preview:
    desc: Preview infrastructure changes
    dir: ${INFRA_DIR}
    cmds:
      - pulumi stack select ${PULUMI_STACK}
      - pulumi preview --diff

  up:
    desc: Deploy infrastructure
    dir: ${INFRA_DIR}
    deps: [preview]
    cmds:
      - pulumi stack select ${PULUMI_STACK}
      - pulumi up --yes

  destroy:
    desc: Destroy all resources
    dir: ${INFRA_DIR}
    cmds:
      - pulumi stack select ${PULUMI_STACK}
      - pulumi destroy --yes

  stack-output:
    desc: Show stack outputs
    dir: ${INFRA_DIR}
    cmds:
      - pulumi stack select ${PULUMI_STACK}
      - pulumi stack output --json

  refresh:
    desc: Refresh state from cloud provider
    dir: ${INFRA_DIR}
    cmds:
      - pulumi stack select ${PULUMI_STACK}
      - pulumi refresh --yes

  lint:
    desc: Lint infrastructure code
    dir: ${INFRA_DIR}
    cmds:
      - ruff check __main__.py
      - mypy __main__.py
    ignore_errors: true

  test:
    desc: Run Pulumi unit tests
    dir: ${INFRA_DIR}
    cmds:
      - pytest tests/ -v

  export:
    desc: Export stack state to JSON
    dir: ${INFRA_DIR}
    cmds:
      - pulumi stack select ${PULUMI_STACK}
      - pulumi stack export --file stack-state.json

  import:
    desc: Import existing resource (use --var RESOURCE_TYPE and --var RESOURCE_ID)
    dir: ${INFRA_DIR}
    cmds:
      - pulumi stack select ${PULUMI_STACK}
      - pulumi import ${RESOURCE_TYPE} ${RESOURCE_ID}

  clean:
    desc: Remove local caches
    dir: ${INFRA_DIR}
    cmds:
      - rm -rf __pycache__/ .pytest_cache/
      - rm -f stack-state.json
```

### infra/__main__.py — Pulumi program (Python)

```markpact:file path=infra/__main__.py
"""Pulumi infrastructure program."""
import pulumi
import pulumi_aws as aws

config = pulumi.Config()
env = pulumi.get_stack().split("/")[-1]

# VPC
vpc = aws.ec2.Vpc(
    f"{env}-vpc",
    cidr_block="10.0.0.0/16",
    enable_dns_hostnames=True,
    tags={"Name": f"{env}-vpc", "Environment": env},
)

# Subnet
subnet = aws.ec2.Subnet(
    f"{env}-subnet",
    vpc_id=vpc.id,
    cidr_block="10.0.1.0/24",
    map_public_ip_on_launch=True,
    tags={"Name": f"{env}-subnet", "Environment": env},
)

# Security Group
sg = aws.ec2.SecurityGroup(
    f"{env}-sg",
    vpc_id=vpc.id,
    ingress=[
        {"protocol": "tcp", "from_port": 80, "to_port": 80, "cidr_blocks": ["0.0.0.0/0"]},
        {"protocol": "tcp", "from_port": 443, "to_port": 443, "cidr_blocks": ["0.0.0.0/0"]},
    ],
    egress=[
        {"protocol": "-1", "from_port": 0, "to_port": 0, "cidr_blocks": ["0.0.0.0/0"]},
    ],
    tags={"Name": f"{env}-sg", "Environment": env},
)

# Export outputs
pulumi.export("vpc_id", vpc.id)
pulumi.export("subnet_id", subnet.id)
pulumi.export("security_group_id", sg.id)
```

### infra/requirements.txt

```markpact:file path=infra/requirements.txt
pulumi>=3.0.0
pulumi-aws>=6.0.0
pytest>=7.0.0
```

### infra/Pulumi.yaml

```markpact:file path=infra/Pulumi.yaml
name: my-infra
runtime:
  name: python
  options:
    virtualenv: venv
description: Multi-environment AWS infrastructure
```

### .env.dev

```markpact:file path=.env.dev
AWS_PROFILE=dev
AWS_DEFAULT_REGION=eu-west-1
PULUMI_CONFIG_PASSPHRASE=dev-secret
```

---

## 📚 Dokumentacja

- [Pulumi Docs](https://www.pulumi.com/docs/)
- [Pulumi AWS Provider](https://www.pulumi.com/registry/packages/aws/)
- [Pulumi Examples](https://github.com/pulumi/examples)

**Licencja:** MIT
