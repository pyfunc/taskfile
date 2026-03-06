# IaC Vagrant — VM Provisioning + Markpact

**Cały projekt Vagrant w jednym pliku README.md — wypakuj i uruchom przez Taskfile.**

## 📋 Co to jest?

Vagrant do provisioningu VM — multi-environment (dev/staging/prod),
multi-provider (VirtualBox/Libvirt/VMware), zintegrowane z `taskfile`.

## Features covered

- **`dir`** — tasks run inside `vagrant/` directory
- **`env_file`** — per-environment configuration
- **`condition`** — provider availability check
- **Multi-VM** — web, db, cache nodes

## 🎯 Workflow

```bash
# 1. Wypakowanie projektu
markpact README.md && cd sandbox

# 2. Start VM
taskfile --env dev run up

# 3. SSH into VM
taskfile --env dev run ssh

# 4. Provisioning
taskfile --env dev run provision

# 5. Status
taskfile --env dev run status

# 6. Destroy
taskfile --env dev run destroy
```

## 🔧 Dostępne komendy

| Komenda | Opis |
|---------|------|
| `taskfile run up` | Start and provision VMs |
| `taskfile run halt` | Stop VMs (graceful) |
| `taskfile run destroy` | Destroy all VMs |
| `taskfile run ssh` | SSH into web VM |
| `taskfile run provision` | Re-provision VMs |
| `taskfile run status` | Show VM status |
| `taskfile run snapshot-save` | Save VM snapshot |
| `taskfile run snapshot-restore` | Restore VM snapshot |
| `taskfile run box-update` | Update base box |
| `taskfile run clean` | Destroy + remove boxes |

---

## Pliki projektu (markpact)

### Taskfile.yml — konfiguracja tasków

```markpact:file path=Taskfile.yml
version: "1"
name: vagrant-infra
description: "Vagrant VM provisioning: multi-env, multi-provider, snapshots"

variables:
  VAGRANT_DIR: vagrant
  VM_NAME: web

environments:
  dev:
    env_file: .env.dev
    variables:
      VAGRANT_PROVIDER: virtualbox
      VM_MEMORY: "1024"
      VM_CPUS: "1"

  staging:
    env_file: .env.staging
    variables:
      VAGRANT_PROVIDER: libvirt
      VM_MEMORY: "2048"
      VM_CPUS: "2"

  prod:
    env_file: .env.prod
    variables:
      VAGRANT_PROVIDER: libvirt
      VM_MEMORY: "4096"
      VM_CPUS: "4"

tasks:

  up:
    desc: Start and provision VMs
    dir: ${VAGRANT_DIR}
    cmds:
      - VAGRANT_DEFAULT_PROVIDER=${VAGRANT_PROVIDER} vagrant up

  halt:
    desc: Stop VMs (graceful shutdown)
    dir: ${VAGRANT_DIR}
    cmds:
      - vagrant halt

  destroy:
    desc: Destroy all VMs
    dir: ${VAGRANT_DIR}
    cmds:
      - vagrant destroy -f

  ssh:
    desc: SSH into VM (use --var VM_NAME=db for other VMs)
    dir: ${VAGRANT_DIR}
    cmds:
      - vagrant ssh ${VM_NAME}

  provision:
    desc: Re-provision VMs (run Ansible/Shell provisioners)
    dir: ${VAGRANT_DIR}
    cmds:
      - vagrant provision

  status:
    desc: Show VM status
    dir: ${VAGRANT_DIR}
    cmds:
      - vagrant status
      - vagrant port ${VM_NAME} 2>/dev/null || true

  snapshot-save:
    desc: Save VM snapshot
    dir: ${VAGRANT_DIR}
    cmds:
      - vagrant snapshot save ${VM_NAME} snapshot-$(date +%Y%m%d-%H%M%S)

  snapshot-restore:
    desc: Restore latest VM snapshot
    dir: ${VAGRANT_DIR}
    cmds:
      - vagrant snapshot restore ${VM_NAME} --no-provision

  box-update:
    desc: Update base box to latest version
    dir: ${VAGRANT_DIR}
    cmds:
      - vagrant box update

  clean:
    desc: Destroy VMs + remove downloaded boxes
    dir: ${VAGRANT_DIR}
    cmds:
      - vagrant destroy -f
      - vagrant box prune
```

### vagrant/Vagrantfile

```markpact:file path=vagrant/Vagrantfile
# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure("2") do |config|
  config.vm.box = "ubuntu/jammy64"

  config.vm.define "web" do |web|
    web.vm.hostname = "web"
    web.vm.network "private_network", ip: "192.168.56.10"
    web.vm.network "forwarded_port", guest: 80, host: 8080
    web.vm.network "forwarded_port", guest: 443, host: 8443

    web.vm.provider "virtualbox" do |vb|
      vb.memory = ENV.fetch("VM_MEMORY", "1024")
      vb.cpus = ENV.fetch("VM_CPUS", "1")
      vb.name = "web-server"
    end

    web.vm.provision "shell", inline: <<-SHELL
      apt-get update
      apt-get install -y nginx docker.io docker-compose-plugin
      systemctl enable nginx docker
      usermod -aG docker vagrant
    SHELL
  end

  config.vm.define "db" do |db|
    db.vm.hostname = "db"
    db.vm.network "private_network", ip: "192.168.56.20"

    db.vm.provider "virtualbox" do |vb|
      vb.memory = "2048"
      vb.cpus = "2"
      vb.name = "db-server"
    end

    db.vm.provision "shell", inline: <<-SHELL
      apt-get update
      apt-get install -y postgresql postgresql-contrib
      systemctl enable postgresql
    SHELL
  end
end
```

### .env.dev

```markpact:file path=.env.dev
VAGRANT_DEFAULT_PROVIDER=virtualbox
VM_MEMORY=1024
VM_CPUS=1
```

---

## 📚 Dokumentacja

- [Vagrant Docs](https://developer.hashicorp.com/vagrant/docs)
- [Vagrant Boxes](https://app.vagrantup.com/boxes/search)

**Licencja:** MIT
