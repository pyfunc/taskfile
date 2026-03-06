# IaC Ansible — Configuration Management + Markpact

**Cały projekt Ansible w jednym pliku README.md — wypakuj i uruchom przez Taskfile.**

## 📋 Co to jest?

Zarządzanie konfiguracją serwerów przez Ansible z multi-environment (dev/staging/prod),
playbooki, role i inventory — wszystko zintegrowane z `taskfile`.

## Features covered

- **`dir`** — all tasks run inside `ansible/` directory
- **`env_file`** — per-environment `.env` files for SSH keys and credentials
- **`condition`** — lint only if ansible-lint is installed
- **`environment_groups`** — `all-prod` for rolling config updates
- **`deps` + `parallel`** — syntax-check + lint run in parallel before deploy
- **`ignore_errors`** — lint doesn't block the pipeline

## 🎯 Workflow

```bash
# 1. Instalacja narzędzi
pip install markpact taskfile --upgrade

# 2. Wypakowanie projektu
markpact README.md
cd sandbox

# 3. Ping hosts
taskfile --env dev run ping

# 4. Deploy
taskfile --env dev run deploy
taskfile --env staging run deploy
taskfile --env prod run deploy

# 5. Rolling deploy to all prod
taskfile -G all-prod run deploy

# 6. Ad-hoc commands
taskfile --env dev run shell --var CMD="uptime"

# 7. Lint & check
taskfile run lint
taskfile run syntax-check
```

## 🔧 Dostępne komendy

| Komenda | Opis |
|---------|------|
| `taskfile run ping` | Ping all hosts in environment |
| `taskfile run deploy` | Run main playbook |
| `taskfile run deploy-tags` | Run playbook with specific tags |
| `taskfile run syntax-check` | Validate playbook syntax |
| `taskfile run lint` | Lint playbooks (ansible-lint) |
| `taskfile run shell` | Run ad-hoc shell command |
| `taskfile run facts` | Gather and display host facts |
| `taskfile run vault-encrypt` | Encrypt secrets with ansible-vault |
| `taskfile run vault-decrypt` | Decrypt secrets with ansible-vault |
| `taskfile run galaxy-install` | Install roles from requirements |
| `taskfile run dry-run` | Check mode (no changes) |
| `taskfile run clean` | Remove retry files and caches |

---

## Pliki projektu (markpact)

### Taskfile.yml — konfiguracja tasków

```markpact:file path=Taskfile.yml
version: "1"
name: ansible-infra
description: "Ansible IaC: multi-env configuration management, playbooks, vault"

variables:
  ANSIBLE_DIR: ansible
  PLAYBOOK: site.yml
  INVENTORY_DIR: inventory
  VAULT_PASSWORD_FILE: .vault_pass
  ANSIBLE_ROLES_PATH: roles
  TAGS: all

environments:
  dev:
    env_file: .env.dev
    variables:
      INVENTORY: ${INVENTORY_DIR}/dev
      SSH_USER: deploy
      BECOME: "true"

  staging:
    env_file: .env.staging
    variables:
      INVENTORY: ${INVENTORY_DIR}/staging
      SSH_USER: deploy
      BECOME: "true"

  prod:
    env_file: .env.prod
    variables:
      INVENTORY: ${INVENTORY_DIR}/prod
      SSH_USER: deploy
      BECOME: "true"

environment_groups:
  all-prod:
    members: [prod]
    strategy: rolling
    max_parallel: 1

tasks:

  ping:
    desc: Ping all hosts in environment
    dir: ${ANSIBLE_DIR}
    cmds:
      - ansible -i ${INVENTORY} all -m ping -u ${SSH_USER}

  deploy:
    desc: Run main playbook
    dir: ${ANSIBLE_DIR}
    deps: [syntax-check]
    cmds:
      - >-
        ansible-playbook -i ${INVENTORY}
        ${PLAYBOOK}
        -u ${SSH_USER}
        --become=${BECOME}
        --vault-password-file=${VAULT_PASSWORD_FILE}

  deploy-tags:
    desc: Run playbook with specific tags (use --var TAGS=nginx,ssl)
    dir: ${ANSIBLE_DIR}
    cmds:
      - >-
        ansible-playbook -i ${INVENTORY}
        ${PLAYBOOK}
        -u ${SSH_USER}
        --become=${BECOME}
        --vault-password-file=${VAULT_PASSWORD_FILE}
        --tags="${TAGS}"

  syntax-check:
    desc: Validate playbook syntax
    dir: ${ANSIBLE_DIR}
    cmds:
      - ansible-playbook --syntax-check -i ${INVENTORY} ${PLAYBOOK}

  lint:
    desc: Lint playbooks (ansible-lint)
    dir: ${ANSIBLE_DIR}
    condition: "command -v ansible-lint >/dev/null 2>&1"
    cmds:
      - ansible-lint ${PLAYBOOK}
    ignore_errors: true

  dry-run:
    desc: Check mode — preview changes without applying
    dir: ${ANSIBLE_DIR}
    cmds:
      - >-
        ansible-playbook -i ${INVENTORY}
        ${PLAYBOOK}
        -u ${SSH_USER}
        --become=${BECOME}
        --vault-password-file=${VAULT_PASSWORD_FILE}
        --check --diff

  shell:
    desc: Run ad-hoc shell command (use --var CMD="uptime")
    dir: ${ANSIBLE_DIR}
    cmds:
      - ansible -i ${INVENTORY} all -m shell -a "${CMD}" -u ${SSH_USER}

  facts:
    desc: Gather and display host facts
    dir: ${ANSIBLE_DIR}
    cmds:
      - ansible -i ${INVENTORY} all -m setup -u ${SSH_USER} | head -100

  vault-encrypt:
    desc: Encrypt file with ansible-vault
    dir: ${ANSIBLE_DIR}
    cmds:
      - ansible-vault encrypt --vault-password-file=${VAULT_PASSWORD_FILE} group_vars/all/vault.yml

  vault-decrypt:
    desc: Decrypt file with ansible-vault
    dir: ${ANSIBLE_DIR}
    cmds:
      - ansible-vault decrypt --vault-password-file=${VAULT_PASSWORD_FILE} group_vars/all/vault.yml

  galaxy-install:
    desc: Install roles from requirements.yml
    dir: ${ANSIBLE_DIR}
    cmds:
      - ansible-galaxy install -r requirements.yml --force

  clean:
    desc: Remove retry files and caches
    dir: ${ANSIBLE_DIR}
    cmds:
      - find . -name "*.retry" -delete
      - rm -rf .ansible/tmp/
```

### ansible/site.yml — główny playbook

```markpact:file path=ansible/site.yml
---
- name: Common setup for all hosts
  hosts: all
  become: true
  roles:
    - common
    - security

- name: Web servers
  hosts: webservers
  become: true
  roles:
    - nginx
    - app

- name: Database servers
  hosts: dbservers
  become: true
  roles:
    - postgresql
```

### ansible/inventory/dev — inventory dla dev

```markpact:file path=ansible/inventory/dev
[webservers]
dev-web-01 ansible_host=192.168.1.10

[dbservers]
dev-db-01 ansible_host=192.168.1.20

[all:vars]
ansible_python_interpreter=/usr/bin/python3
env=dev
```

### ansible/requirements.yml — zależności ról

```markpact:file path=ansible/requirements.yml
---
roles:
  - name: geerlingguy.docker
    version: "7.1.0"
  - name: geerlingguy.nginx
    version: "3.2.0"
  - name: geerlingguy.postgresql
    version: "3.5.0"

collections:
  - name: community.general
    version: "8.0.0"
  - name: ansible.posix
    version: "1.5.0"
```

### .env.dev

```markpact:file path=.env.dev
ANSIBLE_HOST_KEY_CHECKING=False
ANSIBLE_SSH_RETRIES=3
```

---

## 📚 Dokumentacja

- [Ansible Documentation](https://docs.ansible.com/)
- [Ansible Galaxy](https://galaxy.ansible.com/)
- [Ansible Lint](https://ansible.readthedocs.io/projects/lint/)

**Licencja:** MIT
