"""Ansible addon — generates standard configuration management tasks.

Generated tasks:
    ansible-ping, ansible-facts, ansible-provision, ansible-deploy,
    ansible-rollback, ansible-check, ansible-lint, ansible-vault-edit,
    ansible-inventory
"""

from __future__ import annotations


def generate_tasks(config: dict) -> dict[str, dict]:
    """Generate Ansible management tasks from addon config."""
    playbook_dir = config.get("playbook_dir", "ansible")
    inventory = config.get("inventory", "${ANSIBLE_INVENTORY:-inventory/hosts.yml}")
    deploy_playbook = config.get("deploy_playbook", "deploy.yml")
    provision_playbook = config.get("provision_playbook", "provision.yml")
    rollback_playbook = config.get("rollback_playbook", "rollback.yml")
    ssh_key = config.get("ssh_key", "${ANSIBLE_SSH_KEY:-~/.ssh/id_ed25519}")
    become = config.get("become", True)
    extra_vars_str = config.get("extra_vars", "")

    become_flag = "--become" if become else ""
    key_flag = f"--private-key {ssh_key}"
    base_flags = f"-i {inventory} {key_flag} {become_flag}".strip()
    extra_flag = f"-e '{extra_vars_str}'" if extra_vars_str else ""
    full_flags = f"{base_flags} {extra_flag}".strip()

    return {
        "ansible-ping": {
            "desc": "Ping all hosts to verify connectivity",
            "tags": ["ansible", "ops"],
            "cmds": [
                f"ansible all -m ping {base_flags}",
            ],
        },
        "ansible-facts": {
            "desc": "Gather facts from all hosts",
            "tags": ["ansible", "ops"],
            "cmds": [
                f"ansible all -m setup {base_flags}",
            ],
        },
        "ansible-inventory": {
            "desc": "Show parsed inventory",
            "tags": ["ansible", "ops"],
            "silent": True,
            "cmds": [
                f"ansible-inventory -i {inventory} --list",
            ],
        },
        "ansible-provision": {
            "desc": "Run provisioning playbook (server setup)",
            "tags": ["ansible", "setup"],
            "dir": playbook_dir,
            "cmds": [
                f"ansible-playbook {provision_playbook} {full_flags}",
            ],
        },
        "ansible-deploy": {
            "desc": "Run deployment playbook",
            "tags": ["ansible", "deploy"],
            "dir": playbook_dir,
            "cmds": [
                f"ansible-playbook {deploy_playbook} {full_flags}",
            ],
        },
        "ansible-rollback": {
            "desc": "Run rollback playbook",
            "tags": ["ansible", "ops"],
            "dir": playbook_dir,
            "cmds": [
                f"ansible-playbook {rollback_playbook} {full_flags}",
            ],
        },
        "ansible-check": {
            "desc": "Dry-run playbook (check mode, no changes)",
            "tags": ["ansible", "ci"],
            "dir": playbook_dir,
            "cmds": [
                f"ansible-playbook {deploy_playbook} {full_flags} --check --diff",
            ],
        },
        "ansible-lint": {
            "desc": "Lint Ansible playbooks",
            "tags": ["ansible", "ci"],
            "dir": playbook_dir,
            "ignore_errors": True,
            "cmds": [
                "ansible-lint .",
            ],
        },
        "ansible-vault-edit": {
            "desc": "Edit encrypted vault file (--var VAULT_FILE=secrets.yml)",
            "tags": ["ansible", "ops"],
            "dir": playbook_dir,
            "cmds": [
                "ansible-vault edit ${VAULT_FILE:-vault/secrets.yml}",
            ],
        },
    }
