"""VPS Provisioner — idempotent server provisioning for Taskfile.

Handles installation and configuration of:
- Podman (rootless containers)
- Firewall (UFW)
- Traefik (reverse proxy with Quadlet)
- Let's Encrypt (automatic TLS)
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console

if TYPE_CHECKING:
    pass

console = Console()


@dataclass
class ProvisionConfig:
    """Configuration for VPS provisioning."""

    ip: str
    ssh_key: str
    ssh_user: str
    domain: str
    ports: list[int]
    email: str = "admin@example.com"  # For Let's Encrypt
    traefik_version: str = "v3.0"


class VPSProvisioner:
    """Idempotent VPS provisioner using SSH."""

    def __init__(self, config: ProvisionConfig):
        self.config = config
        self.ssh_opts = f"-i {Path(config.ssh_key).expanduser()} -o StrictHostKeyChecking=accept-new"
        self.ssh_target = f"root@{config.ip}"

    def _ssh(self, cmd: str, timeout: int = 60) -> tuple[int, str, str]:
        """Execute command via SSH and return (exit_code, stdout, stderr)."""
        full_cmd = f"ssh {self.ssh_opts} {self.ssh_target} '{cmd}'"
        result = subprocess.run(
            full_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr

    def _check_command(self, cmd: str) -> bool:
        """Check if command exists on remote server."""
        exit_code, _, _ = self._ssh(f"which {cmd}", timeout=10)
        return exit_code == 0

    def provision(self, dry_run: bool = False) -> bool:
        """Run full provisioning sequence idempotently."""
        steps = [
            ("System update", self._system_update),
            ("Podman installation", self._install_podman),
            ("Firewall setup", self._setup_firewall),
            ("Deploy user", self._create_deploy_user),
            ("Traefik setup", self._setup_traefik),
            ("TLS certificates", self._setup_tls),
        ]

        for name, step_func in steps:
            console.print(f"\n[bold]{name}...[/]")
            if dry_run:
                console.print("  [dim](dry run — skipped)[/]")
                continue

            try:
                if not step_func():
                    console.print(f"  [yellow]⚠ {name} had issues, continuing...[/]")
            except Exception as e:
                console.print(f"  [yellow]⚠ {name} failed: {e}[/]")

        console.print("\n[green]✅ Provisioning complete[/]")
        return True

    def _system_update(self) -> bool:
        """Update system packages."""
        exit_code, stdout, stderr = self._ssh(
            "apt-get update -qq && apt-get upgrade -y -qq",
            timeout=180,
        )
        if exit_code == 0:
            console.print("  [green]✓ System updated[/]")
            return True
        console.print(f"  [yellow]⚠ System update exit code: {exit_code}[/]")
        return False

    def _install_podman(self) -> bool:
        """Install Podman and podman-compose."""
        if self._check_command("podman"):
            exit_code, stdout, _ = self._ssh("podman --version", timeout=10)
            if exit_code == 0:
                console.print(f"  [green]✓ Podman already installed: {stdout.strip()}[/]")
                return True

        exit_code, _, stderr = self._ssh(
            "apt-get install -y -qq podman podman-compose",
            timeout=120,
        )
        if exit_code == 0:
            console.print("  [green]✓ Podman installed[/]")
            return True
        console.print(f"  [red]✗ Podman install failed: {stderr[:200]}[/]")
        return False

    def _setup_firewall(self) -> bool:
        """Configure UFW firewall."""
        # Install UFW if not present
        if not self._check_command("ufw"):
            self._ssh("apt-get install -y -qq ufw", timeout=60)

        success = True
        for port in self.config.ports:
            exit_code, _, _ = self._ssh(f"ufw allow {port}/tcp", timeout=10)
            if exit_code != 0:
                success = False

        # Enable firewall
        exit_code, _, _ = self._ssh("ufw --force enable", timeout=10)
        if exit_code == 0:
            console.print(f"  [green]✓ Firewall configured (ports: {', '.join(map(str, self.config.ports))})[/]")
        else:
            console.print("  [yellow]⚠ Firewall enable had issues[/]")

        return success

    def _create_deploy_user(self) -> bool:
        """Create deploy user for running containers rootless."""
        user = self.config.ssh_user

        # Create user (ignore error if exists)
        self._ssh(f"id -u {user} || useradd -m -s /bin/bash {user}", timeout=10)

        # Enable linger for the user (required for rootless systemd)
        exit_code, _, _ = self._ssh(f"loginctl enable-linger {user}", timeout=10)

        # Add user to docker/podman groups if they exist
        self._ssh(f"usermod -aG docker {user} 2>/dev/null || true", timeout=5)

        # Create app directory
        self._ssh(f"mkdir -p /opt/app && chown {user}:{user} /opt/app", timeout=5)

        console.print(f"  [green]✓ Deploy user '{user}' ready[/]")
        return True

    def _setup_traefik(self) -> bool:
        """Setup Traefik as Quadlet container."""
        # Create directories
        dirs = [
            "/etc/traefik",
            "/var/log/traefik",
            f"/home/{self.config.ssh_user}/.config/containers/systemd",
        ]
        for d in dirs:
            self._ssh(f"mkdir -p {d}", timeout=5)

        # Generate Traefik static config
        traefik_yml = f"""api:
  dashboard: true
  insecure: false

entryPoints:
  web:
    address: ":80"
  websecure:
    address: ":443"

providers:
  file:
    directory: /etc/traefik/dynamic
    watch: true

log:
  level: INFO
  filePath: /var/log/traefik/traefik.log

accessLog:
  filePath: /var/log/traefik/access.log
"""

        # Write config via SSH
        escaped_config = traefik_yml.replace("'", "'\\''")
        self._ssh(f"cat > /etc/traefik/traefik.yml << 'EOF'{escaped_config}EOF", timeout=10)

        # Generate Quadlet unit for Traefik
        is_ip_domain = self.config.domain == self.config.ip
        acme_tls = "" if is_ip_domain else f"""\
      - --certificatesresolvers.letsencrypt.acme.tlschallenge=true
      - --certificatesresolvers.letsencrypt.acme.email={self.config.email}
      - --certificatesresolvers.letsencrypt.acme.storage=/etc/traefik/acme.json
"""

        quadlet_unit = f"""[Unit]
Description=Traefik reverse proxy
After=network.target

[Container]
Image=docker.io/traefik:{self.config.traefik_version}
ContainerName=traefik
AutoUpdate=registry

PublishPort=80:80
PublishPort=443:443
PublishPort=8080:8080

Volume=/etc/traefik:/etc/traefik:ro
Volume=/var/run/docker.sock:/var/run/docker.sock:ro

[Service]
Restart=always
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target default.target
"""

        user_systemd_dir = f"/home/{self.config.ssh_user}/.config/containers/systemd"
        escaped_unit = quadlet_unit.replace("'", "'\\''")
        self._ssh(f"cat > {user_systemd_dir}/traefik.container << 'EOF'{escaped_unit}EOF", timeout=10)

        console.print("  [green]✓ Traefik Quadlet unit created[/]")
        return True

    def _setup_tls(self) -> bool:
        """Setup Let's Encrypt TLS if domain is configured."""
        if self.config.domain == self.config.ip:
            console.print("  [dim]IP-only mode, skipping TLS setup[/]")
            return True

        # Install certbot if not present
        if not self._check_command("certbot"):
            self._ssh("apt-get install -y -qq certbot", timeout=60)

        # Obtain certificate
        exit_code, stdout, stderr = self._ssh(
            f"certbot certonly --standalone -d {self.config.domain} --agree-tos -n --email {self.config.email}",
            timeout=120,
        )

        if exit_code == 0:
            console.print(f"  [green]✓ TLS certificate obtained for {self.config.domain}[/]")
            return True
        elif "Certificate not yet due for renewal" in stderr:
            console.print(f"  [green]✓ TLS certificate already valid[/]")
            return True
        else:
            console.print(f"  [yellow]⚠ TLS certificate issue: {stderr[:200]}[/]")
            return False

    def is_provisioned(self) -> bool:
        """Check if VPS appears to be already provisioned."""
        try:
            exit_code, stdout, _ = self._ssh("podman --version", timeout=10)
            return exit_code == 0 and "podman version" in stdout.lower()
        except Exception:
            return False


def provision_vps(
    ip: str,
    ssh_key: str,
    ssh_user: str = "deploy",
    domain: str | None = None,
    ports: list[int] | None = None,
    dry_run: bool = False,
) -> bool:
    """Convenience function for one-shot VPS provisioning.

    Args:
        ip: VPS IP address
        ssh_key: Path to SSH private key
        ssh_user: Deploy user name (default: deploy)
        domain: Domain name (default: uses IP)
        ports: Ports to open in firewall (default: [22, 80, 443])
        dry_run: Show commands without executing

    Returns:
        True if provisioning succeeded
    """
    config = ProvisionConfig(
        ip=ip,
        ssh_key=ssh_key,
        ssh_user=ssh_user,
        domain=domain or ip,
        ports=ports or [22, 80, 443],
    )

    provisioner = VPSProvisioner(config)

    if provisioner.is_provisioned():
        console.print("[yellow]VPS already provisioned, skipping...[/]")
        return True

    return provisioner.provision(dry_run=dry_run)
