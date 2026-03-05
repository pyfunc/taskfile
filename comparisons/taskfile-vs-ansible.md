# Taskfile vs Ansible

## Quick Comparison

| Feature | Ansible | Taskfile |
|---------|---------|----------|
| YAML playbooks | ✅ | ✅ |
| SSH execution | ✅ | ✅ |
| Agentless | ✅ | ✅ |
| **Fleet management** | ✅ (100+ hosts) | ✅ (<50 hosts) |
| **Idempotent modules** | ✅ | ❌ |
| **Complex inventories** | ✅ | ⚠️ (groups) |
| **Learning curve** | Steep | Low |
| **Environments** | Manual | ✅ |
| **Registry authentication** | ❌ | ✅ |
| **Quadlet generation** | ⚠️ (custom) | ✅ |
| **VPS setup** | ⚠️ (playbook) | ✅ (one-command) |
| **CI/CD generation** | ❌ | ✅ |

## What is Ansible?

Ansible is an open-source IT automation platform for configuration management, application deployment, and orchestration.

**Key strengths:**
- Powerful idempotent modules
- Large module ecosystem
- Complex inventory management
- Role-based organization
- Enterprise-grade features (Tower/AWX)
- Proven at scale (thousands of hosts)

## When to Use Ansible

- 100+ servers to manage
- Complex provisioning requirements
- Idempotent configuration management
- Role-based infrastructure organization
- Enterprise environments with strict requirements
- Need for extensive module library

## When to Use Taskfile Instead

- Small fleets (<50 devices)
- Simple SSH commands
- Quick deployments without provisioning
- Lower learning curve preferred
- Podman Quadlet generation
- Registry authentication
- VPS one-command setup
- CI/CD config generation
- Daily operations over provisioning

## Side-by-Side Examples

### Basic Command Execution

```yaml
# Ansible playbook
---
- name: Deploy application
  hosts: prod
  tasks:
    - name: Pull container image
      command: podman pull myapp:v1.0
      
    - name: Restart service
      systemd:
        name: myapp
        state: restarted
        scope: user
```

```yaml
# Taskfile.yml
environments:
  prod:
    ssh_host: prod.example.com
    ssh_user: deploy

tasks:
  deploy:
    env: [prod]
    cmds:
      - "@remote podman pull ${IMAGE}:${TAG}"
      - "@remote systemctl --user restart ${APP}"
```

### Fleet Deploy

```yaml
# Ansible inventory (inventory.yml)
all:
  children:
    kiosks:
      hosts:
        kiosk1:
          ansible_host: 192.168.1.10
        kiosk2:
          ansible_host: 192.168.1.11
        kiosk3:
          ansible_host: 192.168.1.12
```

```yaml
# Ansible playbook
---
- name: Deploy to kiosks
  hosts: kiosks
  serial: 2  # Rolling: 2 at a time
  tasks:
    - name: Pull image
      command: podman pull myapp:v1.0
    
    - name: Restart service
      systemd:
        name: myapp
        state: restarted
```

```yaml
# Taskfile.yml
environments:
  kiosk1: {ssh_host: 192.168.1.10, ssh_user: pi}
  kiosk2: {ssh_host: 192.168.1.11, ssh_user: pi}
  kiosk3: {ssh_host: 192.168.1.12, ssh_user: pi}

environment_groups:
  kiosks:
    members: [kiosk1, kiosk2, kiosk3]
    strategy: rolling
    max_parallel: 2

tasks:
  deploy:
    cmds:
      - "@remote podman pull ${IMAGE}:${TAG}"
      - "@remote systemctl --user restart ${APP}"
```

Usage:
```bash
# Deploy with rolling strategy
taskfile -G kiosks run deploy --var TAG=v1.0
```

### Fleet Status Check

```yaml
# Ansible playbook
---
- name: Check kiosk health
  hosts: kiosks
  gather_facts: yes
  tasks:
    - name: Get temperature
      command: vcgencmd measure_temp
      register: temp
      
    - name: Check disk usage
      command: df -h /
      register: disk
      
    - name: Check memory
      command: free -h
      register: memory
      
    - name: Display results
      debug:
        msg: "{{ inventory_hostname }}: {{ temp.stdout }}, Disk: {{ disk.stdout }}"
```

```bash
# Taskfile - Built-in fleet status
taskfile fleet status --group kiosks

# Output:
# ┌─────────────────┬──────────────┬────────┬──────┬─────┬──────┐
# │ Name            │ IP           │ Status │ Temp │ RAM │ Disk │
# ├─────────────────┼──────────────┼────────┼──────┼─────┼──────┤
# │ kiosk1          │ 192.168.1.10 │ ✅ UP  │ 52°C │ 41% │ 23%  │
# │ kiosk2          │ 192.168.1.11 │ ✅ UP  │ 48°C │ 38% │ 19%  │
```

### Auto-Repair

```yaml
# Ansible playbook - Manual repair tasks
---
- name: Repair kiosk
  hosts: kiosk1
  tasks:
    - name: Check disk space
      command: df -h /
      
    - name: Clean up if needed
      command: podman system prune -f
      when: ansible_mounts[0].size_available < 1000000000
      
    - name: Restart podman
      systemd:
        name: podman
        state: restarted
        scope: user
```

```bash
# Taskfile - Interactive repair
taskfile fleet repair kiosk1

# Auto-fix without prompts
taskfile fleet repair kiosk1 --auto-fix
```

## Key Differences

### Ansible's Advantages
1. **Idempotency** - Run playbooks multiple times safely
2. **Module ecosystem** - 3000+ modules for everything
3. **Complex inventories** - Dynamic inventories, groups, patterns
4. **Roles** - Reusable, shareable components
5. **Enterprise features** - AWX/Tower for scheduling, RBAC
6. **Scale** - Proven with thousands of nodes
7. **Dry run** - `--check` mode for safe testing

### Taskfile's Advantages
1. **Simplicity** - Lower learning curve
2. **Speed** - Faster for simple SSH commands
3. **Built-in fleet commands** - `status`, `repair`, `list`
4. **Environment abstraction** - `local`, `staging`, `prod`
5. **Registry auth** - Interactive token setup
6. **Quadlet generation** - docker-compose → systemd
7. **VPS setup** - One-command provisioning
8. **CI/CD generation** - GitHub Actions, GitLab CI
9. **No dependencies** - Single Python package

## Recommended Combo: Ansible + Taskfile

Use Ansible for provisioning, Taskfile for daily operations:

```yaml
# Taskfile.yml
tasks:
  provision:
    desc: Initial server setup with Ansible
    cmds:
      - ansible-playbook -i inventory.yml provision.yml
  
  deploy:
    desc: Deploy application
    env: [prod]
    cmds:
      - "@remote podman pull ${IMAGE}:${TAG}"
      - "@remote systemctl --user restart ${APP}"
  
  status:
    desc: Check fleet health
    cmds:
      - taskfile fleet status --group production
```

```yaml
# Ansible provision.yml
---
- name: Provision VPS
  hosts: prod
  become: yes
  tasks:
    - name: Update system
      apt:
        update_cache: yes
        upgrade: dist
    
    - name: Install Podman
      apt:
        name: podman
        state: present
    
    - name: Create deploy user
      user:
        name: deploy
        groups: sudo
        append: yes
```

## Migration from Ansible to Taskfile

### When to Migrate

Consider migrating when:
- Fleet is small (<50 devices)
- Ansible feels too heavy
- Simple SSH commands suffice
- No need for idempotent modules
- Faster iteration needed

### How to Migrate

**1. Convert inventory to environments**

```yaml
# Ansible inventory
kiosks:
  hosts:
    kiosk1:
      ansible_host: 192.168.1.10
      ansible_user: pi
```

```yaml
# Taskfile environments
environments:
  kiosk1:
    ssh_host: 192.168.1.10
    ssh_user: pi
```

**2. Convert playbooks to tasks**

```yaml
# Ansible
- command: podman pull myapp:v1.0
```

```yaml
# Taskfile
cmds:
  - "@remote podman pull ${IMAGE}:${TAG}"
```

**3. Use environment_groups for fleet**

```yaml
environment_groups:
  kiosks:
    members: [kiosk1, kiosk2, kiosk3]
    strategy: rolling
```

## Summary

| Use Case | Recommendation |
|----------|----------------|
| 100+ servers | Ansible ✅ |
| Complex provisioning | Ansible ✅ |
| Idempotent config mgmt | Ansible ✅ |
| Enterprise environments | Ansible ✅ |
| Small fleets (<50) | Taskfile ✅ |
| Quick daily operations | Taskfile ✅ |
| Simple SSH deploys | Taskfile ✅ |
| RPi kiosks/edge devices | Taskfile ✅ |
| Podman Quadlet | Taskfile ✅ |
| VPS one-command setup | Taskfile ✅ |
| Registry publishing | Taskfile ✅ |

## Verdict

**For hybrid approach:**

```
Ansible → Provisioning, complex config management
Taskfile → Daily ops, deploys, fleet management
```

**Choose Ansible if:**
- Large scale (100+ nodes)
- Complex provisioning needed
- Idempotency is critical
- Enterprise features required

**Choose Taskfile if:**
- Small to medium fleets
- Simple SSH-based operations
- Faster learning/setup time
- Edge/IoT deployments
- Registry/VPS integration
