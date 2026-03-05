"""Fleet management CLI commands for taskfile.

Manages a fleet of devices (e.g. Raspberry Pi) via fleet.yml.
"""

from __future__ import annotations

import sys

import click
from rich.console import Console

from taskfile.cli.main import main
from taskfile.fleet import (
    FleetConfig,
    add_device,
    deploy_to_group,
    fleet_status,
    load_fleet,
    print_fleet_status,
    save_fleet,
)

console = Console()


def _load_fleet_or_exit(fleet_path: str | None) -> FleetConfig:
    """Load fleet.yml or exit with error."""
    try:
        return load_fleet(fleet_path)
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/] {e}")
        console.print("[dim]Create fleet.yml or use 'taskfile fleet add' to start.[/]")
        sys.exit(1)


@main.group()
def fleet():
    """Manage a fleet of devices (RPi, edge nodes, kiosks).

    \b
    Commands:
        taskfile fleet status               — Show all device statuses
        taskfile fleet add <ip> --name xxx  — Add device to fleet
        taskfile fleet deploy --group xxx   — Deploy app to group
        taskfile fleet sync                 — Reconcile desired vs actual state
    """
    pass


@fleet.command(name="status")
@click.option("-f", "--fleet-file", default=None, help="Path to fleet.yml")
def fleet_status_cmd(fleet_file):
    """Show status of all fleet devices.

    \b
    Examples:
        taskfile fleet status
        taskfile fleet status -f /path/to/fleet.yml
    """
    config = _load_fleet_or_exit(fleet_file)

    if not config.devices:
        console.print("[yellow]No devices in fleet. Use 'taskfile fleet add' to add one.[/]")
        sys.exit(0)

    console.print(f"[bold]Checking {len(config.devices)} device(s)...[/]\n")
    statuses = fleet_status(config)
    print_fleet_status(statuses)


@fleet.command(name="add")
@click.argument("ip")
@click.option("--name", required=True, help="Device name (e.g. kiosk-lobby)")
@click.option("--group", default="default", help="Device group")
@click.option("--apps", default="monitoring-agent", help="Comma-separated app list")
@click.option("-f", "--fleet-file", default=None, help="Path to fleet.yml")
def fleet_add_cmd(ip, name, group, apps, fleet_file):
    """Add a new device to the fleet.

    \b
    Examples:
        taskfile fleet add 192.168.1.50 --name kiosk-lobby --group kiosks
        taskfile fleet add 10.0.0.5 --name sensor-1 --group sensors --apps goal-sensor,monitoring-agent
    """
    try:
        config = load_fleet(fleet_file)
    except FileNotFoundError:
        console.print("[yellow]fleet.yml not found — creating new fleet file[/]")
        config = FleetConfig()

    if name in config.devices:
        console.print(f"[yellow]Device '{name}' already exists. Updating...[/]")

    app_list = [a.strip() for a in apps.split(",") if a.strip()]
    device = add_device(config, name=name, host=ip, group=group, apps=app_list)

    path = save_fleet(config, fleet_file)
    console.print(f"[green]✓ Added {device.name} ({device.host}) to {path}[/]")
    console.print(f"  [dim]Group: {device.group}, Apps: {', '.join(device.apps)}[/]")
    console.print(f"\n[dim]Deploy apps with:[/]  taskfile fleet deploy --device {name} --app {app_list[0]}")


@fleet.command(name="deploy")
@click.option("--group", default=None, help="Target device group")
@click.option("--device", default=None, help="Target specific device")
@click.option("--app", required=True, help="App to deploy")
@click.option("--tag", default="latest", help="Image tag")
@click.option("-f", "--fleet-file", default=None, help="Path to fleet.yml")
def fleet_deploy_cmd(group, device, app, tag, fleet_file):
    """Deploy an app to fleet devices.

    \b
    Examples:
        taskfile fleet deploy --group kiosks --app goal-kiosk --tag v1.2.0
        taskfile fleet deploy --device kiosk-lobby --app goal-kiosk
    """
    config = _load_fleet_or_exit(fleet_file)

    if not group and not device:
        console.print("[red]Error: specify --group or --device[/]")
        sys.exit(1)

    success = deploy_to_group(
        config,
        group_name=group,
        device_name=device,
        app_name=app,
        tag=tag,
    )
    sys.exit(0 if success else 1)


@fleet.command(name="sync")
@click.option("-f", "--fleet-file", default=None, help="Path to fleet.yml")
@click.option("--tag", default="latest", help="Image tag for missing apps")
def fleet_sync_cmd(fleet_file, tag):
    """Sync desired state — install missing apps, report unknown containers.

    \b
    Examples:
        taskfile fleet sync
        taskfile fleet sync --tag v1.2.0
    """
    config = _load_fleet_or_exit(fleet_file)

    from taskfile.fleet import _ssh_cmd

    for name, dev in config.devices.items():
        desired = set(dev.apps)

        try:
            result = _ssh_cmd(
                config, dev.host,
                'podman ps --format "{{.Names}}"',
                timeout=10,
            )
            running = set(result.stdout.strip().split("\n")) if result.stdout.strip() else set()
        except Exception:
            console.print(f"[red]✗ {name}: unreachable[/]")
            continue

        missing = desired - running
        extra = running - desired - {""}

        if missing:
            console.print(f"📡 {name}: installing {missing}")
            for app_name in missing:
                deploy_to_group(config, device_name=name, app_name=app_name, tag=tag)

        if extra:
            console.print(f"🧹 {name}: unexpected containers: {extra}")

        if not missing and not extra:
            console.print(f"[green]✓ {name}: in sync[/]")


@fleet.command(name="list")
@click.option("-f", "--fleet-file", default=None, help="Path to fleet.yml")
def fleet_list_cmd(fleet_file):
    """List all devices, groups, and apps in the fleet.

    \b
    Examples:
        taskfile fleet list
    """
    config = _load_fleet_or_exit(fleet_file)

    if config.devices:
        console.print("\n[bold]Devices:[/]")
        for name, dev in sorted(config.devices.items()):
            apps = ", ".join(dev.apps) if dev.apps else "[dim]none[/]"
            console.print(f"  [cyan]{name:20s}[/] {dev.host:16s} group={dev.group:12s} apps={apps}")

    if config.groups:
        console.print("\n[bold]Groups:[/]")
        for name, grp in sorted(config.groups.items()):
            console.print(
                f"  [magenta]{name:20s}[/] strategy={grp.update_strategy:10s} "
                f"max_parallel={grp.max_parallel}"
            )

    if config.apps:
        console.print("\n[bold]Apps:[/]")
        for name, app in sorted(config.apps.items()):
            ports = ", ".join(app.ports) if app.ports else "none"
            console.print(f"  [green]{name:20s}[/] {app.image:40s} ports={ports}")

    if not config.devices:
        console.print("[yellow]Fleet is empty. Add devices with: taskfile fleet add <ip> --name <name>[/]")
