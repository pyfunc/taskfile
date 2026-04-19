"""Reusable deployment utilities — image transfer, remote checks, .env management.

Extracted from sandbox shell scripts into native Python so projects don't
need to duplicate deploy.sh, doctor.sh, setup-prod.sh, setup-hosts.sh, etc.

Usage from CLI commands or programmatically:
    from taskfile.deploy_utils import (
        transfer_image_via_ssh,
        test_ssh_connection,
        check_remote_podman,
        check_remote_disk,
        install_remote_podman,
        update_env_var,
        load_env_file,
        setup_ssh_key,
    )
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import NamedTuple

from rich.console import Console

console = Console()


# ─── .env file management ─────────────────────────────────────────


def load_env_file(path: str | Path = ".env") -> dict[str, str]:
    """Load a .env file into a dict. Skips comments and empty lines."""
    env_path = Path(path)
    if not env_path.exists():
        return {}
    result: dict[str, str] = {}
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            result[key.strip()] = value.strip()
    return result


def update_env_var(key: str, value: str, env_file: str | Path = ".env") -> None:
    """Update or append a variable in an .env file."""
    env_path = Path(env_file)
    if not env_path.exists():
        env_path.write_text(f"{key}={value}\n")
        return

    lines = env_path.read_text().splitlines()
    found = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            found = True
            break
    if not found:
        lines.append(f"{key}={value}")
    env_path.write_text("\n".join(lines) + "\n")


def remove_env_var(key: str, env_file: str | Path = ".env") -> None:
    """Remove a variable from an .env file."""
    env_path = Path(env_file)
    if not env_path.exists():
        return
    lines = env_path.read_text().splitlines()
    lines = [line for line in lines if not line.strip().startswith(f"{key}=")]
    env_path.write_text("\n".join(lines) + "\n")


# ─── SSH utilities ──────────────────────────────────────────────────


class SSHResult(NamedTuple):
    """Result of an SSH operation."""

    success: bool
    output: str
    exit_code: int


def test_ssh_connection(
    host: str,
    user: str = "root",
    port: int = 22,
    timeout: int = 5,
) -> SSHResult:
    """Test SSH key-based connection to a remote host."""
    target = f"{user}@{host}"
    try:
        result = subprocess.run(
            [
                "ssh",
                "-o",
                f"ConnectTimeout={timeout}",
                "-o",
                "BatchMode=yes",
                "-o",
                "StrictHostKeyChecking=accept-new",
                "-p",
                str(port),
                target,
                "echo ok",
            ],
            capture_output=True,
            text=True,
            timeout=timeout + 5,
        )
        return SSHResult(
            success=result.returncode == 0,
            output=result.stdout.strip(),
            exit_code=result.returncode,
        )
    except subprocess.TimeoutExpired:
        return SSHResult(success=False, output="Connection timeout", exit_code=-1)
    except Exception as e:
        return SSHResult(success=False, output=str(e), exit_code=-1)


def ssh_exec(
    host: str,
    command: str,
    user: str = "root",
    port: int = 22,
    timeout: int = 30,
) -> SSHResult:
    """Execute a command on a remote host via SSH."""
    target = f"{user}@{host}"
    try:
        result = subprocess.run(
            [
                "ssh",
                "-o",
                f"ConnectTimeout={min(timeout, 10)}",
                "-o",
                "BatchMode=yes",
                "-o",
                "StrictHostKeyChecking=accept-new",
                "-p",
                str(port),
                target,
                command,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        combined = (result.stdout + result.stderr).strip()
        return SSHResult(
            success=result.returncode == 0,
            output=combined,
            exit_code=result.returncode,
        )
    except subprocess.TimeoutExpired:
        return SSHResult(success=False, output="Command timeout", exit_code=-1)
    except Exception as e:
        return SSHResult(success=False, output=str(e), exit_code=-1)


def setup_ssh_key(
    host: str,
    user: str = "root",
    key_type: str = "ed25519",
) -> bool:
    """Generate SSH key if missing and copy to remote host.

    Returns True if SSH key auth works after setup.
    """
    key_path = Path.home() / ".ssh" / f"id_{key_type}"

    # Generate key if missing
    if not key_path.exists() and not (Path.home() / ".ssh" / "id_rsa").exists():
        console.print(f"  Generating SSH key ({key_type})...")
        subprocess.run(
            [
                "ssh-keygen",
                "-t",
                key_type,
                "-C",
                f"deploy@{os.uname().nodename}",
                "-f",
                str(key_path),
                "-N",
                "",
            ],
            capture_output=True,
        )

    # Copy key to remote
    target = f"{user}@{host}"
    console.print(f"  Copying SSH key to {target}...")
    console.print("  [dim](you may need to enter the server password once)[/]")
    try:
        process = subprocess.Popen(
            ["ssh-copy-id", target],
            stdin=None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        process.wait(timeout=120)
    except Exception:
        return False

    # Verify
    result = test_ssh_connection(host, user)
    return result.success


# ─── Remote host checks ────────────────────────────────────────────


class RemoteInfo(NamedTuple):
    """Information about the remote host."""

    podman_installed: bool
    podman_version: str
    disk_available: str
    images: list[str]


def check_remote_podman(
    host: str,
    user: str = "root",
    port: int = 22,
) -> tuple[bool, str]:
    """Check if podman is installed on the remote host.

    Returns (installed, version_string).
    """
    result = ssh_exec(host, "podman --version 2>/dev/null || echo NOT_FOUND", user, port)
    if result.success and "NOT_FOUND" not in result.output:
        return True, result.output.strip()
    return False, ""


def check_remote_disk(
    host: str,
    user: str = "root",
    port: int = 22,
) -> str:
    """Check available disk space on the remote host."""
    result = ssh_exec(host, "df -h / | tail -1 | awk '{print $4}'", user, port)
    return result.output.strip() if result.success else "unknown"


def list_remote_images(
    host: str,
    user: str = "root",
    port: int = 22,
) -> list[str]:
    """List container images on remote host."""
    result = ssh_exec(
        host,
        "podman images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null || true",
        user,
        port,
    )
    if result.success and result.output:
        return [line.strip() for line in result.output.splitlines() if line.strip()]
    return []


def check_remote_info(
    host: str,
    user: str = "root",
    port: int = 22,
) -> RemoteInfo:
    """Gather full remote host information."""
    podman_ok, podman_ver = check_remote_podman(host, user, port)
    disk = check_remote_disk(host, user, port)
    images = list_remote_images(host, user, port) if podman_ok else []
    return RemoteInfo(
        podman_installed=podman_ok,
        podman_version=podman_ver,
        disk_available=disk,
        images=images,
    )


def install_remote_podman(
    host: str,
    user: str = "root",
    port: int = 22,
) -> bool:
    """Install podman on the remote host (Debian/Ubuntu).

    Returns True if podman is available after installation.
    """
    ssh_exec(
        host,
        "apt-get update -qq && apt-get install -y -qq podman 2>&1 | tail -3",
        user,
        port,
        timeout=120,
    )
    # Verify installation
    ok, _ = check_remote_podman(host, user, port)
    return ok


# ─── Docker image transfer ─────────────────────────────────────────


def transfer_image_via_ssh(
    image: str,
    host: str,
    user: str = "root",
    port: int = 22,
    remote_runtime: str = "podman",
) -> bool:
    """Transfer a Docker image to a remote host via SSH pipe.

    Equivalent to: docker save IMAGE | ssh USER@HOST 'podman load'

    Returns True on success.
    """
    target = f"{user}@{host}"
    ssh_opts = [
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-p",
        str(port),
    ]
    cmd = f"docker save {image} | ssh {' '.join(ssh_opts)} {target} '{remote_runtime} load'"

    console.print(f"  📦 Transferring {image} → {host}...")

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=600,  # 10 min timeout for large images
        )
        if result.returncode == 0:
            console.print(f"  [green]✓[/] {image} transferred")
            return True
        else:
            console.print(f"  [red]✗[/] Transfer failed: {result.stdout}")
            return False
    except subprocess.TimeoutExpired:
        console.print("  [red]✗[/] Transfer timeout (>10min)")
        return False
    except Exception as e:
        console.print(f"  [red]✗[/] Transfer error: {e}")
        return False


def transfer_images_via_ssh(
    images: list[str],
    host: str,
    user: str = "root",
    port: int = 22,
    remote_runtime: str = "podman",
) -> bool:
    """Transfer multiple Docker images to a remote host.

    Returns True if all transfers succeeded.
    """
    all_ok = True
    for image in images:
        if not transfer_image_via_ssh(image, host, user, port, remote_runtime):
            all_ok = False
    return all_ok


# ─── Remote container management ───────────────────────────────────


def deploy_container_remote(
    host: str,
    image: str,
    container_name: str,
    port_mapping: str,
    user: str = "root",
    port: int = 22,
    runtime: str = "podman",
) -> bool:
    """Deploy a container on a remote host.

    Args:
        host: Remote hostname
        image: Full image name (e.g. docker.io/library/myapp:latest)
        container_name: Container name
        port_mapping: Port mapping (e.g. "8000:8000")
        user: SSH user
        port: SSH port
        runtime: Container runtime (podman/docker)

    Returns True on success.
    """
    cmd = f"{runtime} run -d --name {container_name} --replace -p {port_mapping} {image}"
    result = ssh_exec(host, cmd, user, port, timeout=60)
    return result.success


def stop_container_remote(
    host: str,
    container_name: str,
    user: str = "root",
    port: int = 22,
    runtime: str = "podman",
) -> bool:
    """Stop and remove a container on a remote host."""
    ssh_exec(host, f"{runtime} stop {container_name} 2>/dev/null || true", user, port)
    ssh_exec(host, f"{runtime} rm {container_name} 2>/dev/null || true", user, port)
    return True


def get_remote_logs(
    host: str,
    container_name: str,
    user: str = "root",
    port: int = 22,
    runtime: str = "podman",
    tail: int = 20,
) -> str:
    """Get logs from a remote container."""
    result = ssh_exec(
        host,
        f"{runtime} logs --tail {tail} {container_name} 2>&1",
        user,
        port,
        timeout=30,
    )
    return result.output if result.success else f"(failed to get logs: {result.output})"


def get_remote_status(
    host: str,
    container_names: list[str],
    user: str = "root",
    port: int = 22,
    runtime: str = "podman",
) -> str:
    """Get container status on a remote host."""
    filters = " ".join(f"--filter name={n}" for n in container_names)
    result = ssh_exec(
        host,
        f"{runtime} ps {filters} --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}\\t{{{{.Ports}}}}'",
        user,
        port,
    )
    return result.output if result.success else f"(failed to get status: {result.output})"


# ─── Project cleanup ───────────────────────────────────────────────


def clean_project(
    level: int = 1,
    project_dir: str | Path = ".",
) -> list[str]:
    """Clean project artifacts.

    Levels:
        1 — Remove generated apps/ only
        2 — Remove apps/ + .venv/
        3 — Full reset (everything except README.md)

    Returns list of removed paths.
    """
    project = Path(project_dir)
    removed: list[str] = []

    targets_by_level = {
        1: ["apps"],
        2: ["apps", ".venv"],
        3: [
            "apps",
            ".venv",
            "scripts",
            "prompts",
            "docker-compose.yml",
            "project.yml",
            ".env",
            ".gitignore",
            ".port-state.json",
            "Taskfile.yml",
        ],
    }

    targets = targets_by_level.get(level, targets_by_level[1])

    for target in targets:
        path = project / target
        if path.is_dir():
            shutil.rmtree(path)
            removed.append(str(target))
        elif path.is_file():
            path.unlink()
            removed.append(str(target))

    # For level 3, also docker compose down
    if level >= 3:
        subprocess.run(
            ["docker", "compose", "down", "-v"],
            capture_output=True,
            cwd=str(project),
        )

    return removed
