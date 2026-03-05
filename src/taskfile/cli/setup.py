"""Setup command for taskfile — one-command VPS provisioning and deploy.

Example:
    taskfile setup 123.45.67.89
    taskfile setup 123.45.67.89 --domain app.example.com
    taskfile setup 123.45.67.89 --ssh-key ~/.ssh/id_ed25519 --user deploy
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from taskfile.cli.main import console, main
from taskfile.provisioner import VPSProvisioner, ProvisionConfig

if TYPE_CHECKING:
    pass


class SetupConfig:
    """Configuration collected during setup process."""

    def __init__(
        self,
        ip: str,
        ssh_key: str,
        user: str,
        domain: str,
        ports: list[int],
        env_local: str,
        env_prod: str,
    ):
        self.ip = ip
        self.ssh_key = ssh_key
        self.user = user
        self.domain = domain
        self.ports = ports
        self.env_local = env_local
        self.env_prod = env_prod


def _validate_ip(ip: str) -> bool:
    """Validate IP address format."""
    pattern = r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
    return bool(re.match(pattern, ip))


def _validate_ssh_key(path: str) -> bool:
    """Check if SSH key file exists."""
    expanded = os.path.expanduser(path)
    return Path(expanded).is_file()


def _collect_interactive_setup(ip: str | None) -> SetupConfig:
    """Collect setup configuration through interactive prompts."""
    console.print(Panel.fit(
        "[bold green]Taskfile Setup[/]\n[dim]One-command VPS provisioning[/]",
        border_style="green"
    ))

    # IP address
    if ip is None:
        ip = Prompt.ask("VPS IP address")
    else:
        console.print(f"VPS IP: [cyan]{ip}[/]")

    if not _validate_ip(ip):
        console.print(f"[red]Invalid IP address: {ip}[/]")
        sys.exit(1)

    # SSH key
    default_key = "~/.ssh/id_ed25519"
    if not _validate_ssh_key(default_key):
        default_key = "~/.ssh/id_rsa"
    if not _validate_ssh_key(default_key):
        default_key = ""

    ssh_key = Prompt.ask("SSH key path", default=default_key or "~/.ssh/id_ed25519")
    if not _validate_ssh_key(ssh_key):
        console.print(f"[red]SSH key not found: {ssh_key}[/]")
        sys.exit(1)

    # User
    user = Prompt.ask("Deploy user", default="deploy")

    # Domain
    default_domain = ip
    domain = Prompt.ask("Domain (or press Enter to use IP)", default=default_domain)

    # Ports
    ports_str = Prompt.ask("Ports to open", default="22,80,443")
    try:
        ports = [int(p.strip()) for p in ports_str.split(",")]
    except ValueError:
        console.print("[yellow]Invalid ports format, using defaults[/]")
        ports = [22, 80, 443]

    # Generate env files preview
    console.print("\n[bold]Generated environment files:[/]")

    env_local = f"""# Local development environment
DOMAIN=localhost
WEB_PORT=3000
API_PORT=8000
"""

    env_prod = f"""# Production environment
DOMAIN={domain}
VPS_IP={ip}
SSH_USER={user}
SSH_HOST={ip}
SSH_KEY={ssh_key}
WEB_PORT=3000
API_PORT=8000
"""

    console.print(f"\n[dim].env.local:[/]\n{env_local}")
    console.print(f"[dim].env.prod:[/]\n{env_prod}")

    if not Confirm.ask("\nProceed with setup?", default=True):
        console.print("[yellow]Setup cancelled[/]")
        sys.exit(0)

    return SetupConfig(
        ip=ip,
        ssh_key=ssh_key,
        user=user,
        domain=domain,
        ports=ports,
        env_local=env_local,
        env_prod=env_prod,
    )


def _write_env_files(config: SetupConfig) -> None:
    """Write .env.local and .env.prod files."""
    env_local_path = Path(".env.local")
    env_prod_path = Path(".env.prod")

    if env_local_path.exists():
        if not Confirm.ask(f"{env_local_path} exists. Overwrite?", default=False):
            console.print(f"[yellow]Skipping {env_local_path}[/]")
        else:
            env_local_path.write_text(config.env_local)
            console.print(f"[green]✓[/] Updated {env_local_path}")
    else:
        env_local_path.write_text(config.env_local)
        console.print(f"[green]✓[/] Created {env_local_path}")

    if env_prod_path.exists():
        if not Confirm.ask(f"{env_prod_path} exists. Overwrite?", default=False):
            console.print(f"[yellow]Skipping {env_prod_path}[/]")
        else:
            env_prod_path.write_text(config.env_prod)
            console.print(f"[green]✓[/] Updated {env_prod_path}")
    else:
        env_prod_path.write_text(config.env_prod)
        console.print(f"[green]✓[/] Created {env_prod_path}")


def _provision_ssh_key(config: SetupConfig, dry_run: bool = False) -> bool:
    """Copy SSH key to VPS using ssh-copy-id."""
    console.print("\n[bold]Step 1/5: SSH key provisioning[/]")

    key_path = os.path.expanduser(config.ssh_key)
    target = f"root@{config.ip}"

    cmd = f"ssh-copy-id -i {key_path} {target}"

    console.print(f"  [dim]→ {cmd}[/]")

    if dry_run:
        console.print("  [dim](dry run — skipped)[/]")
        return True

    # Inform user about password prompt
    console.print("\n  [yellow]⚠ You may be prompted for the VPS root password[/]")
    console.print("  [dim]   (this is expected for first-time SSH key setup)[/]\n")

    try:
        # Use Popen for interactive input instead of run with capture_output
        import subprocess
        process = subprocess.Popen(
            cmd,
            shell=True,
            stdin=sys.stdin,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        result = process.wait(timeout=120)

        if result == 0:
            console.print("\n  [green]✓ SSH key copied successfully[/]")
            return True
        else:
            console.print(f"\n  [yellow]⚠ ssh-copy-id may have failed (exit {result})[/]")
            # Continue anyway - key might already be present
            return True
    except subprocess.TimeoutExpired:
        console.print("\n  [red]✗ SSH connection timeout[/]")
        return False
    except Exception as e:
        console.print(f"\n  [red]✗ SSH key copy failed: {e}[/]")
        return False


def _test_ssh_connection(config: SetupConfig, dry_run: bool = False) -> bool:
    """Test SSH connection to VPS."""
    console.print("\n[bold]Step 2/5: Testing SSH connection[/]")

    key_path = os.path.expanduser(config.ssh_key)
    cmd = f"ssh -i {key_path} -o StrictHostKeyChecking=accept-new root@{config.ip} 'echo OK'"

    console.print(f"  [dim]→ {cmd}[/]")

    if dry_run:
        console.print("  [dim](dry run — skipped)[/]")
        return True

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and "OK" in result.stdout:
            console.print("  [green]✓ SSH connection successful[/]")
            return True
        else:
            console.print(f"  [red]✗ SSH connection failed (exit {result.returncode})[/]")
            if result.stderr:
                console.print(f"  [dim]{result.stderr}[/]")
            return False
    except subprocess.TimeoutExpired:
        console.print("  [red]✗ SSH connection timeout[/]")
        return False
    except Exception as e:
        console.print(f"  [red]✗ SSH connection failed: {e}[/]")
        return False


def _provision_vps(config: SetupConfig, dry_run: bool = False) -> bool:
    """Provision VPS using VPSProvisioner."""
    provision_config = ProvisionConfig(
        ip=config.ip,
        ssh_key=config.ssh_key,
        ssh_user=config.user,
        domain=config.domain,
        ports=config.ports,
    )
    provisioner = VPSProvisioner(provision_config)
    return provisioner.provision(dry_run=dry_run)


def _is_vps_ready(config: SetupConfig) -> bool:
    """Check if VPS is already provisioned."""
    provision_config = ProvisionConfig(
        ip=config.ip,
        ssh_key=config.ssh_key,
        ssh_user=config.user,
        domain=config.domain,
        ports=config.ports,
    )
    provisioner = VPSProvisioner(provision_config)
    return provisioner.is_provisioned()


def _deploy_application(config: SetupConfig, dry_run: bool = False) -> bool:
    """Deploy application using taskfile deploy."""
    console.print("\n[bold]Step 4/5: Deploying application[/]")

    if dry_run:
        console.print("  [dim]→ taskfile --env prod deploy (dry run)[/]")
        console.print("  [dim](dry run — skipped)[/]")
        return True

    try:
        result = subprocess.run(
            ["taskfile", "--env", "prod", "deploy"],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            console.print("  [green]✓ Application deployed[/]")
            return True
        else:
            console.print(f"  [red]✗ Deploy failed (exit {result.returncode})[/]")
            if result.stderr:
                console.print(f"  [dim]{result.stderr[:500]}[/]")
            return False
    except FileNotFoundError:
        console.print("  [red]✗ taskfile command not found[/]")
        return False
    except subprocess.TimeoutExpired:
        console.print("  [red]✗ Deploy timeout[/]")
        return False
    except Exception as e:
        console.print(f"  [red]✗ Deploy failed: {e}[/]")
        return False


def _print_summary(config: SetupConfig) -> None:
    """Print setup completion summary."""
    console.print("\n[bold green]✅ Setup complete![/]")
    console.print(f"\n[bold]Your application:[/]")
    console.print(f"  [dim]VPS IP:[/]     {config.ip}")
    console.print(f"  [dim]Domain:[/]     {config.domain}")
    console.print(f"  [dim]Deploy user:[/] {config.user}")

    if config.domain != config.ip:
        console.print(f"\n  [green]https://{config.domain}[/] — Landing page")
        console.print(f"  [green]https://app.{config.domain}[/] — Web application")
    else:
        console.print(f"\n  [green]http://{config.ip}[/] — Application")

    console.print(f"\n[dim]Next steps:[/]")
    console.print(f"  taskfile logs       — View logs")
    console.print(f"  taskfile --env prod run status — Check production status")


def _parse_ports(ports: str) -> list[int]:
    """Parse comma-separated port string into list of ints."""
    try:
        return [int(p.strip()) for p in ports.split(",")]
    except ValueError:
        console.print("[red]Invalid ports format. Use: --ports 22,80,443[/]")
        sys.exit(1)


def _build_config_from_args(
    ip: str, ssh_key: str, user: str, domain: str | None, port_list: list[int]
) -> SetupConfig:
    """Build SetupConfig from CLI arguments (non-interactive path)."""
    if not _validate_ip(ip):
        console.print(f"[red]Invalid IP address: {ip}[/]")
        sys.exit(1)

    if not _validate_ssh_key(ssh_key):
        console.print(f"[red]SSH key not found: {ssh_key}[/]")
        sys.exit(1)

    actual_domain = domain or ip

    env_local = f"""# Local development environment
DOMAIN=localhost
WEB_PORT=3000
API_PORT=8000
"""

    env_prod = f"""# Production environment
DOMAIN={actual_domain}
VPS_IP={ip}
SSH_USER={user}
SSH_HOST={ip}
SSH_KEY={ssh_key}
WEB_PORT=3000
API_PORT=8000
"""

    return SetupConfig(
        ip=ip,
        ssh_key=ssh_key,
        user=user,
        domain=actual_domain,
        ports=port_list,
        env_local=env_local,
        env_prod=env_prod,
    )


def _execute_setup_steps(
    config: SetupConfig, dry_run: bool, skip_provision: bool, skip_deploy: bool
) -> bool:
    """Run all setup steps in sequence. Returns True if all succeeded."""
    if not _provision_ssh_key(config, dry_run=dry_run):
        return False

    if not _test_ssh_connection(config, dry_run=dry_run):
        return False

    if not skip_provision:
        if _is_vps_ready(config):
            console.print("\n[yellow]VPS already provisioned, skipping...[/]")
        elif not _provision_vps(config, dry_run=dry_run):
            return False

    if not skip_deploy:
        if not _deploy_application(config, dry_run=dry_run):
            console.print("\n[yellow]Deploy skipped or failed. You can retry later with:[/]")
            console.print("  taskfile --env prod deploy")

    return True


@main.command()
@click.argument("ip", required=False)
@click.option("--ssh-key", default="~/.ssh/id_ed25519", help="Path to SSH key")
@click.option("--user", default="deploy", help="Deploy user name")
@click.option("--domain", default=None, help="Domain name (defaults to IP)")
@click.option("--ports", default="22,80,443", help="Comma-separated ports to open")
@click.option("--dry-run", is_flag=True, help="Show commands without executing")
@click.option("--skip-provision", is_flag=True, help="Skip VPS provisioning")
@click.option("--skip-deploy", is_flag=True, help="Skip application deploy")
def setup(
    ip: str | None,
    ssh_key: str,
    user: str,
    domain: str | None,
    ports: str,
    dry_run: bool,
    skip_provision: bool,
    skip_deploy: bool,
):
    """One-command VPS setup: SSH key → provision → deploy.

    IP can be provided as argument or interactively.

    \b
    Examples:
        taskfile setup 123.45.67.89
        taskfile setup 123.45.67.89 --domain app.example.com
        taskfile setup --ssh-key ~/.ssh/custom_key --user admin
    """
    port_list = _parse_ports(ports)

    if ip is None:
        config = _collect_interactive_setup(None)
    else:
        config = _build_config_from_args(ip, ssh_key, user, domain, port_list)

    _write_env_files(config)
    success = _execute_setup_steps(config, dry_run, skip_provision, skip_deploy)
    _print_summary(config)

    sys.exit(0 if success else 1)
