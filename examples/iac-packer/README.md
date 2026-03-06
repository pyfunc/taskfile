# IaC Packer — Machine Image Building + Markpact

**Cały projekt Packer w jednym pliku README.md — wypakuj i uruchom przez Taskfile.**

## 📋 Co to jest?

HashiCorp Packer do budowania obrazów maszyn (AMI, Docker, Vagrant boxes).
Multi-provider, multi-environment, zintegrowane z `taskfile`.

## Features covered

- **`dir`** — tasks run inside `packer/` directory
- **`env_file`** — per-environment cloud credentials
- **`condition`** — provider-specific checks
- **`deps`** — validate before build
- **Multi-builder** — AMI + Docker + Vagrant

## 🎯 Workflow

```bash
# 1. Wypakowanie projektu
markpact README.md && cd sandbox

# 2. Init (download plugins)
taskfile run init

# 3. Validate
taskfile --env aws run validate

# 4. Build AMI
taskfile --env aws run build

# 5. Build Docker image
taskfile --env docker run build

# 6. Inspect
taskfile run inspect
```

## 🔧 Dostępne komendy

| Komenda | Opis |
|---------|------|
| `taskfile run init` | Initialize Packer plugins |
| `taskfile run validate` | Validate Packer templates |
| `taskfile run build` | Build machine image |
| `taskfile run inspect` | Inspect template variables |
| `taskfile run fmt` | Format HCL templates |
| `taskfile run clean` | Remove build artifacts |

---

## Pliki projektu (markpact)

### Taskfile.yml — konfiguracja tasków

```markpact:file path=Taskfile.yml
version: "1"
name: packer-images
description: "Packer: multi-provider machine image building (AMI, Docker, Vagrant)"

variables:
  PACKER_DIR: packer
  TEMPLATE: main.pkr.hcl

environments:
  aws:
    env_file: .env.aws
    variables:
      BUILDER: amazon-ebs
      AWS_REGION: eu-west-1
      SOURCE_AMI_FILTER: ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*
      INSTANCE_TYPE: t3.micro

  docker:
    env_file: .env.docker
    variables:
      BUILDER: docker
      BASE_IMAGE: ubuntu:22.04

  vagrant:
    variables:
      BUILDER: vagrant
      BOX: ubuntu/jammy64

tasks:

  init:
    desc: Initialize Packer plugins
    dir: ${PACKER_DIR}
    cmds:
      - packer init .

  validate:
    desc: Validate Packer templates
    dir: ${PACKER_DIR}
    cmds:
      - packer validate -var "builder=${BUILDER}" .

  build:
    desc: Build machine image
    dir: ${PACKER_DIR}
    deps: [validate]
    cmds:
      - packer build -var "builder=${BUILDER}" -force .

  inspect:
    desc: Inspect template variables and builders
    dir: ${PACKER_DIR}
    cmds:
      - packer inspect .

  fmt:
    desc: Format HCL templates
    dir: ${PACKER_DIR}
    cmds:
      - packer fmt -recursive .

  clean:
    desc: Remove build artifacts
    dir: ${PACKER_DIR}
    cmds:
      - rm -rf output-*
      - rm -f manifest.json
```

### packer/main.pkr.hcl — Packer template

```markpact:file path=packer/main.pkr.hcl
packer {
  required_plugins {
    amazon = {
      source  = "github.com/hashicorp/amazon"
      version = "~> 1"
    }
    docker = {
      source  = "github.com/hashicorp/docker"
      version = "~> 1"
    }
  }
}

variable "builder" {
  type    = string
  default = "docker"
}

variable "base_image" {
  type    = string
  default = "ubuntu:22.04"
}

variable "aws_region" {
  type    = string
  default = "eu-west-1"
}

variable "instance_type" {
  type    = string
  default = "t3.micro"
}

source "docker" "ubuntu" {
  image  = var.base_image
  commit = true
  changes = [
    "EXPOSE 80 443",
    "CMD [\"/usr/sbin/nginx\", \"-g\", \"daemon off;\"]"
  ]
}

source "amazon-ebs" "ubuntu" {
  region        = var.aws_region
  instance_type = var.instance_type
  source_ami_filter {
    filters = {
      name                = "ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"
      root-device-type    = "ebs"
      virtualization-type = "hvm"
    }
    owners      = ["099720109477"]
    most_recent = true
  }
  ssh_username = "ubuntu"
  ami_name     = "myapp-{{timestamp}}"
  tags = {
    Name        = "myapp"
    Environment = "packer-build"
    Builder     = "taskfile"
  }
}

build {
  sources = ["source.docker.ubuntu", "source.amazon-ebs.ubuntu"]

  provisioner "shell" {
    inline = [
      "apt-get update",
      "apt-get install -y nginx curl ca-certificates",
      "systemctl enable nginx || true"
    ]
  }

  post-processor "manifest" {
    output = "manifest.json"
  }
}
```

### .env.aws

```markpact:file path=.env.aws
AWS_PROFILE=packer
AWS_DEFAULT_REGION=eu-west-1
```

### .env.docker

```markpact:file path=.env.docker
DOCKER_BUILDKIT=1
```

---

## 📚 Dokumentacja

- [Packer Docs](https://developer.hashicorp.com/packer/docs)
- [Packer Builders](https://developer.hashicorp.com/packer/plugins)

**Licencja:** MIT
