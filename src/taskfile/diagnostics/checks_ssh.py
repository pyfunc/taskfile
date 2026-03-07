"""SSH-related diagnostic checks — extracted from checks.py for modularity."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from taskfile.diagnostics.models import (
    Issue,
    IssueCategory,
    FixStrategy,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
)

if TYPE_CHECKING:
    from taskfile.models import TaskfileConfig


def check_ssh_keys() -> list[Issue]:
    """Check SSH keys exist."""
    issues: list[Issue] = []
    ssh_dir = Path.home() / ".ssh"
    if not ssh_dir.exists():
        issues.append(Issue(
            category=IssueCategory.CONFIG_ERROR,
            message="~/.ssh directory not found",
            fix_strategy=FixStrategy.CONFIRM,
            severity=SEVERITY_ERROR,
            fix_command="mkdir -p ~/.ssh && chmod 700 ~/.ssh",
            teach=(
                "SSH directory (~/.ssh) stores your SSH keys and config. "
                "It must exist before generating keys. The chmod 700 ensures "
                "only you can access it — SSH refuses to use insecure directories."
            ),
            layer=3,
        ))
        return issues

    keys = list(ssh_dir.glob("id_*"))
    if not keys:
        issues.append(Issue(
            category=IssueCategory.CONFIG_ERROR,
            message="No SSH keys found (~/.ssh/id_*)",
            fix_strategy=FixStrategy.CONFIRM,
            severity=SEVERITY_WARNING,
            fix_command="ssh-keygen -t ed25519 -N ''",
            fix_description="Generate an SSH key pair",
            teach=(
                "SSH keys authenticate you to remote servers without passwords. "
                "Generate a key pair, then copy the public key to the server "
                "with 'ssh-copy-id'. Ed25519 is the modern, secure key format."
            ),
            layer=3,
        ))
    return issues


def _test_ssh(env) -> int | None:
    """Quick SSH connection test. Returns exit code or None on exception."""
    try:
        result = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes",
             "-o", "StrictHostKeyChecking=no",
             f"-p", str(env.ssh_port),
             f"{env.ssh_user}@{env.ssh_host}", "true"],
            capture_output=True, timeout=10,
        )
        return result.returncode
    except Exception:
        return None


def check_ssh_connectivity(config: "TaskfileConfig") -> list[Issue]:
    """Check SSH connectivity — distinguish: missing key vs refused vs auth fail."""
    from taskfile.diagnostics.checks import _resolve_env_fields

    issues: list[Issue] = []
    taskfile_dir = Path(config.source_path).parent if config.source_path else Path.cwd()
    for env_name, env in config.environments.items():
        if not env.is_remote:
            continue
        _resolve_env_fields(env, taskfile_dir)
        ssh_key = env.ssh_key or "~/.ssh/id_ed25519"
        key_path = Path(os.path.expanduser(ssh_key))
        if not key_path.exists():
            issues.append(Issue(
                category=IssueCategory.CONFIG_ERROR,
                message=f"SSH key {ssh_key} not found for env '{env_name}'",
                fix_strategy=FixStrategy.CONFIRM,
                severity=SEVERITY_WARNING,
                fix_command=f"ssh-keygen -t ed25519 -f {ssh_key} -N ''",
                context={"env": env_name, "host": env.ssh_host},
                teach=(
                    "SSH keys authenticate you to remote servers. "
                    "Generate a key pair, then use 'ssh-copy-id' to authorize it "
                    "on the remote server before attempting remote deployment."
                ),
                layer=3,
            ))
            continue

        rc = _test_ssh(env)
        if rc == 255:  # connection refused
            issues.append(Issue(
                category=IssueCategory.EXTERNAL_ERROR,
                message=f"SSH to {env.ssh_host}: connection refused",
                fix_strategy=FixStrategy.LLM,
                severity=SEVERITY_ERROR,
                context={"host": env.ssh_host, "env": env_name, "error": "connection_refused"},
                teach=(
                    "Connection refused means the server is reachable but SSH daemon "
                    "is not running or the port is blocked. Check: 1) Is the server "
                    "up? 2) Is SSH service running? 3) Is firewall blocking port 22? "
                    "4) Is the correct hostname/IP configured in Taskfile?"
                ),
                layer=3,
            ))
        elif rc == 5:  # auth failed
            issues.append(Issue(
                category=IssueCategory.CONFIG_ERROR,
                message=f"SSH auth failed for {env.ssh_host}",
                fix_strategy=FixStrategy.CONFIRM,
                severity=SEVERITY_ERROR,
                fix_command=f"ssh-copy-id -i {ssh_key} {env.ssh_user}@{env.ssh_host}",
                context={"host": env.ssh_host, "env": env_name},
                teach=(
                    "SSH authentication failed — the key is not authorized on the server. "
                    "Copy your public key to the server with 'ssh-copy-id'. "
                    "Ensure the remote server has your key in ~/.ssh/authorized_keys."
                ),
                layer=3,
            ))
        elif rc != 0 and rc is not None:
            issues.append(Issue(
                category=IssueCategory.EXTERNAL_ERROR,
                message=f"SSH to {env.ssh_host}: failed (exit {rc})",
                fix_strategy=FixStrategy.LLM,
                severity=SEVERITY_WARNING,
                context={"host": env.ssh_host, "env": env_name, "exit_code": rc},
                layer=3,
            ))
    return issues


def check_remote_health(config: "TaskfileConfig") -> list[Issue]:
    """Check remote host health — podman, disk space, container status."""
    from taskfile.diagnostics.checks import _resolve_env_fields

    issues: list[Issue] = []
    taskfile_dir = Path(config.source_path).parent if config.source_path else Path.cwd()
    for env_name, env in config.environments.items():
        if not env.is_remote:
            continue
        _resolve_env_fields(env, taskfile_dir)

        from taskfile.deploy_utils import (
            check_remote_podman,
            check_remote_disk,
            test_ssh_connection,
        )

        # Quick SSH check first
        ssh_result = test_ssh_connection(env.ssh_host, env.ssh_user, env.ssh_port)
        if not ssh_result.success:
            continue  # SSH checks are handled by check_ssh_connectivity

        # Podman
        podman_ok, podman_ver = check_remote_podman(env.ssh_host, env.ssh_user, env.ssh_port)
        if not podman_ok:
            issues.append(Issue(
                category=IssueCategory.DEPENDENCY_MISSING,
                message=f"Podman not installed on {env.ssh_host} (env: {env_name})",
                fix_strategy=FixStrategy.CONFIRM,
                severity=SEVERITY_WARNING,
                fix_command=f"ssh {env.ssh_user}@{env.ssh_host} 'apt install -y podman'",
                fix_description="Install podman on the remote server",
                teach=(
                    "Podman is a container runtime used on the remote server to run containers. "
                    "It's a Docker alternative preferred for rootless operation. "
                    "Install it via your distribution's package manager."
                ),
                context={"host": env.ssh_host, "env": env_name},
                layer=3,
            ))

        # Disk space
        disk = check_remote_disk(env.ssh_host, env.ssh_user, env.ssh_port)
        if disk and disk != "unknown":
            # Parse disk value — warn if < 1G
            try:
                val = disk.rstrip("GMKTBgmktb")
                unit = disk[len(val):].upper()
                num = float(val)
                if unit.startswith("M") and num < 500:
                    issues.append(Issue(
                        category=IssueCategory.EXTERNAL_ERROR,
                        message=f"Low disk on {env.ssh_host}: {disk} free",
                        fix_strategy=FixStrategy.MANUAL,
                        severity=SEVERITY_WARNING,
                        fix_description="Free disk space or expand volume",
                        teach=(
                            "Low disk space on the remote server may cause deployment failures "
                            "when pulling new images or writing files. Clean up unused images "
                            "with 'podman system prune' or expand the disk."
                        ),
                        context={"host": env.ssh_host, "disk": disk},
                        layer=3,
                    ))
                elif unit.startswith("K"):
                    issues.append(Issue(
                        category=IssueCategory.EXTERNAL_ERROR,
                        message=f"Critical disk on {env.ssh_host}: {disk} free",
                        fix_strategy=FixStrategy.MANUAL,
                        severity=SEVERITY_ERROR,
                        fix_description="Immediately free disk space",
                        teach=(
                            "Critical disk space on the remote server will prevent any new "
                            "deployments and may crash existing services. Urgent cleanup needed "
                            "with 'podman system prune' and removing logs."
                        ),
                        context={"host": env.ssh_host, "disk": disk},
                        layer=3,
                    ))
            except (ValueError, IndexError):
                pass

        # DNS resolution inside containers (critical for ACME/Let's Encrypt)
        try:
            dns_result = subprocess.run(
                ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes",
                 "-o", "StrictHostKeyChecking=no",
                 f"-p", str(env.ssh_port),
                 f"{env.ssh_user}@{env.ssh_host}",
                 "podman exec traefik nslookup acme-v02.api.letsencrypt.org 8.8.8.8 2>&1 | head -1"],
                capture_output=True, text=True, timeout=15,
            )
            if dns_result.returncode != 0 or "timed out" in dns_result.stdout.lower():
                issues.append(Issue(
                    category=IssueCategory.EXTERNAL_ERROR,
                    message=f"Container DNS broken on {env.ssh_host} — Let's Encrypt will fail",
                    fix_strategy=FixStrategy.MANUAL,
                    severity=SEVERITY_WARNING,
                    fix_description=(
                        "Mount a resolv.conf with public DNS into traefik container:\n"
                        "  echo 'nameserver 8.8.8.8' > deploy/resolv.conf\n"
                        "  Add to traefik.container: Volume=.../resolv.conf:/etc/resolv.conf:ro\n"
                        "  Also check: ufw route allow in on podman1 out on <iface> from 10.89.0.0/24"
                    ),
                    teach=(
                        "Podman containers on a named bridge network use an internal DNS server "
                        "(10.89.0.x) that only resolves container names, not external domains. "
                        "For Let's Encrypt ACME to work, traefik needs to reach "
                        "acme-v02.api.letsencrypt.org. Fix: mount a resolv.conf with 8.8.8.8 "
                        "into the container. Also ensure the host firewall allows FORWARD traffic "
                        "from the podman subnet."
                    ),
                    context={"host": env.ssh_host, "env": env_name},
                    layer=3,
                ))
        except Exception:
            pass  # Container might not exist yet — skip silently

    return issues
