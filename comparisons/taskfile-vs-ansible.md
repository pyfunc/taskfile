# Taskfile vs Ansible

## Quick Comparison

| Feature | Ansible | Taskfile |
|---------|---------|----------|
| Configuration language | YAML (playbooks) | YAML (Taskfile.yml) |
| Agent required | ❌ (agentless via SSH) | ❌ (agentless via SSH) |
| SSH execution | ✅ (core) | ✅ (`@remote` + embedded paramiko) |
| Connection pooling | ✅ (persistent connections) | ✅ (paramiko pool, `pip install taskfile[ssh]`) |
| **Retries + delay** | ✅ (`retries`, `delay`) | ✅ (`retries`, `retry_delay`) |
| **Timeout** | ✅ (`timeout`) | ✅ (`timeout`) |
| **Tags** | ✅ (`tags`, `--tags`) | ✅ (`tags`, `--tags`) |
| **Register output** | ✅ (`register`) | ✅ (`register`) |
| **Conditions** | ✅ (`when`) | ✅ (`condition`) |
| Handlers / Notify | ✅ | ❌ |
| Roles / Collections | ✅ (Galaxy) | ✅ (`include`, `functions`) |
| Templates (Jinja2) | ✅ | ❌ (`${VAR}` substitution) |
| Vault (secrets) | ✅ (ansible-vault) | ❌ (use env vars / .env files) |
| Facts (auto-detect) | ✅ (gather_facts) | ❌ |
| Inventory management | ✅ (hosts, groups) | ✅ (`environments`, `environment_groups`) |
| Rolling updates | ✅ (`serial`) | ✅ (`strategy: rolling`) |
| Canary deploys | ❌ (manual) | ✅ (`strategy: canary`) |
| Parallel execution | ✅ (`forks`) | ✅ (`parallel: true`) |
| **Embedded functions** | ✅ (modules: Python) | ✅ (`functions` section: Python/shell/Node) |
| **CI/CD generation** | ❌ | ✅ (6 platforms) |
| **CI/CD import** | ❌ | ✅ (`taskfile import`) |
| Fleet management | ✅ (inventory groups) | ✅ (`environment_groups` + strategies) |
| Container runtime | ❌ (via modules) | ✅ (Docker/Podman native) |
| Quadlet generation | ❌ | ✅ |
| Registry authentication | ❌ (via modules) | ✅ (`taskfile auth`) |
| Learning curve | Steep | Low |
| Dependencies | Python + many packages | Python + PyYAML + click |

## What is Ansible?

Ansible is an IT automation platform for configuration management, application deployment, and orchestration. It uses SSH to execute tasks on remote hosts without requiring an agent.

**Key strengths:**
- Massive module ecosystem (3000+ modules)
- Idempotent by design
- Inventory management with dynamic sources
- Vault for encrypted secrets
- Jinja2 templating
- Roles and Collections for reuse
- Galaxy marketplace

## When to Use Ansible

- Large-scale server configuration management (100+ hosts)
- Idempotent system state management
- Complex multi-step provisioning with Jinja2 templates
- Teams already using Ansible Tower/AWX
- When you need 3000+ built-in modules
- Network device configuration (Cisco, Juniper, etc.)

## When to Use Taskfile Instead

- Application deployment (build → test → deploy)
- CI/CD pipeline definition and generation
- Container-first workflows (Docker/Podman)
- Fleet management with deployment strategies (rolling/canary/parallel)
- Multi-environment deploys (local → staging → prod)
- Registry authentication and publishing
- Simpler YAML without Jinja2 complexity
- Embedded functions (Python/shell/Node inline)
- Importing existing CI/CD configs into a single format

## Feature Mapping: Ansible → Taskfile

### Inventory → Environments + Groups

```yaml
# Ansible inventory.yml
all:
  children:
    webservers:
      hosts:
        web1: {ansible_host: 192.168.1.10}
        web2: {ansible_host: 192.168.1.11}
    dbservers:
      hosts:
        db1: {ansible_host: 192.168.1.20}
```

```yaml
# Taskfile.yml
environments:
  web1:
    ssh_host: 192.168.1.10
  web2:
    ssh_host: 192.168.1.11
  db1:
    ssh_host: 192.168.1.20

environment_groups:
  webservers:
    members: [web1, web2]
    strategy: rolling
  dbservers:
    members: [db1]
```

### Playbook Tasks → Taskfile Tasks

```yaml
# Ansible playbook
- name: Deploy app
  hosts: webservers
  tasks:
    - name: Pull image
      command: docker pull myapp:latest
      retries: 3
      delay: 5
      register: pull_result

    - name: Restart service
      command: systemctl restart myapp
      when: pull_result.changed
      tags: [deploy]
```

```yaml
# Taskfile.yml
tasks:
  pull:
    desc: Pull latest image
    retries: 3
    retry_delay: 5
    register: PULL_OUTPUT
    tags: [deploy]
    cmds:
      - "@remote docker pull myapp:latest"

  restart:
    desc: Restart service
    deps: [pull]
    tags: [deploy]
    cmds:
      - "@remote systemctl restart myapp"
```

### Modules → Functions

```yaml
# Ansible — Python module
- name: Send Slack notification
  community.general.slack:
    token: "{{ slack_token }}"
    msg: "Deploy complete"
```

```yaml
# Taskfile.yml — embedded Python function
functions:
  notify-slack:
    lang: python
    code: |
      import os, json, urllib.request
      data = json.dumps({"text": f"Deploy {os.environ['APP_NAME']} complete"})
      req = urllib.request.Request(os.environ['SLACK_WEBHOOK'],
            data=data.encode(), headers={"Content-Type": "application/json"})
      urllib.request.urlopen(req)

tasks:
  deploy:
    cmds:
      - docker push ${IMAGE}:${TAG}
      - "@fn notify-slack"
```

### Tags → Tags

```bash
# Ansible
ansible-playbook site.yml --tags "deploy,restart"

# Taskfile
taskfile run deploy restart --tags deploy
```

### Retries → Retries

```yaml
# Ansible
- command: curl http://app/health
  retries: 5
  delay: 10
  register: health

# Taskfile
tasks:
  health-check:
    retries: 5
    retry_delay: 10
    register: HEALTH_OUTPUT
    cmds:
      - curl -sf http://app/health
```

## Integration: Taskfile + Ansible

Use both tools where each excels:

```yaml
# Taskfile.yml — orchestration layer
tasks:
  provision:
    desc: Provision servers with Ansible
    cmds:
      - ansible-playbook -i inventory.yml provision.yml

  deploy:
    desc: Deploy application
    deps: [build, test]
    cmds:
      - "@remote docker pull ${IMAGE}:${TAG}"
      - "@remote systemctl restart ${APP_NAME}"

  full-setup:
    desc: Provision + Deploy
    deps: [provision]
    cmds:
      - taskfile run deploy
```

**Division of responsibility:**
- **Ansible** — system-level configuration (packages, users, firewall, certificates)
- **Taskfile** — application deployment, CI/CD, container management, fleet updates

## Migration Guide: Ansible → Taskfile

| Ansible Concept | Taskfile Equivalent |
|----------------|---------------------|
| `inventory.yml` | `environments` + `environment_groups` |
| `playbook.yml` | `Taskfile.yml` (tasks section) |
| `roles/` | `include` (split into files) |
| `modules` | `functions` section |
| `vars/` | `variables` section |
| `handlers` | tasks with `condition` |
| `tags` | `tags` on tasks + `--tags` CLI |
| `register` | `register` on tasks |
| `retries` + `delay` | `retries` + `retry_delay` |
| `timeout` | `timeout` |
| `when` | `condition` |
| `serial` | `strategy: rolling` + `max_parallel` |
| `ansible-vault` | `.env` files (gitignored) |
| `ansible-galaxy` | `include` + `functions` |
| `--check` (dry run) | `--dry-run` |
| `--limit` | `--env` / `-G` |
