"""Fleet management — models and operations for managing device fleets.

Reads fleet.yml as the source of truth for all managed devices.
Supports device groups with rolling/canary/parallel update strategies.
"""

from __future__ import annotations

import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console
from rich.table import Table

console = Console()


# ─── Data Models ──────────────────────────────────────


@dataclass
class FleetApp:
    """Container application definition for fleet devices."""

    name: str
    image: str = ""
    container_runtime: str = "podman"
    ports: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    restart: str = "no"


@dataclass
class DeviceGroup:
    """Group of devices sharing update strategy."""

    name: str
    description: str = ""
    update_strategy: str = "parallel"  # rolling | parallel | canary
    max_parallel: int = 5
    canary_count: int = 1


@dataclass
class Device:
    """A single managed device in the fleet."""

    name: str
    host: str
    group: str = "default"
    apps: list[str] = field(default_factory=list)
    variables: dict[str, str] = field(default_factory=dict)


@dataclass
class FleetConfig:
    """Parsed fleet.yml configuration."""

    ssh_user: str = "pi"
    ssh_key: str = "~/.ssh/id_rpi_fleet"
    default_arch: str = "arm64"
    devices: dict[str, Device] = field(default_factory=dict)
    groups: dict[str, DeviceGroup] = field(default_factory=dict)
    apps: dict[str, FleetApp] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FleetConfig:
        """Parse raw YAML dict into FleetConfig."""
        fleet_data = data.get("fleet", data)

        config = cls(
            ssh_user=fleet_data.get("ssh_user", "pi"),
            ssh_key=fleet_data.get("ssh_key", "~/.ssh/id_rpi_fleet"),
            default_arch=fleet_data.get("default_arch", "arm64"),
        )

        # Parse devices
        for name, dev_data in fleet_data.get("devices", {}).items():
            if isinstance(dev_data, dict):
                config.devices[name] = Device(
                    name=name,
                    host=dev_data.get("host", ""),
                    group=dev_data.get("group", "default"),
                    apps=dev_data.get("apps", []),
                    variables=dev_data.get("vars", dev_data.get("variables", {})),
                )

        # Parse groups
        for name, grp_data in fleet_data.get("groups", {}).items():
            if isinstance(grp_data, dict):
                config.groups[name] = DeviceGroup(
                    name=name,
                    description=grp_data.get("desc", grp_data.get("description", "")),
                    update_strategy=grp_data.get("update_strategy", "parallel"),
                    max_parallel=grp_data.get("max_parallel", 5),
                    canary_count=grp_data.get("canary_count", 1),
                )

        # Parse apps
        for name, app_data in fleet_data.get("apps", {}).items():
            if isinstance(app_data, dict):
                config.apps[name] = FleetApp(
                    name=name,
                    image=app_data.get("image", ""),
                    container_runtime=app_data.get("container_runtime", "podman"),
                    ports=app_data.get("ports", []),
                    env=app_data.get("env", {}),
                    restart=app_data.get("restart", "no"),
                )

        return config


# ─── Fleet file I/O ───────────────────────────────────


def load_fleet(path: str | Path | None = None) -> FleetConfig:
    """Load fleet.yml from the given path or search current directory."""
    if path is None:
        path = Path("fleet.yml")
    path = Path(path)

    if not path.is_file():
        raise FileNotFoundError(f"Fleet file not found: {path}")

    with open(path) as f:
        data = yaml.safe_load(f) or {}

    return FleetConfig.from_dict(data)


def save_fleet(config: FleetConfig, path: str | Path | None = None) -> Path:
    """Save FleetConfig back to fleet.yml."""
    if path is None:
        path = Path("fleet.yml")
    path = Path(path)

    data: dict[str, Any] = {
        "fleet": {
            "ssh_user": config.ssh_user,
            "ssh_key": config.ssh_key,
            "default_arch": config.default_arch,
            "devices": {},
            "groups": {},
            "apps": {},
        }
    }

    for name, dev in config.devices.items():
        dev_dict: dict[str, Any] = {"host": dev.host, "group": dev.group}
        if dev.apps:
            dev_dict["apps"] = dev.apps
        if dev.variables:
            dev_dict["vars"] = dev.variables
        data["fleet"]["devices"][name] = dev_dict

    for name, grp in config.groups.items():
        data["fleet"]["groups"][name] = {
            "desc": grp.description,
            "update_strategy": grp.update_strategy,
            "max_parallel": grp.max_parallel,
        }

    for name, app in config.apps.items():
        app_dict: dict[str, Any] = {
            "image": app.image,
            "container_runtime": app.container_runtime,
        }
        if app.ports:
            app_dict["ports"] = app.ports
        if app.env:
            app_dict["env"] = app.env
        if app.restart != "no":
            app_dict["restart"] = app.restart
        data["fleet"]["apps"][name] = app_dict

    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))
    return path


# ─── SSH helpers ──────────────────────────────────────


def _ssh_cmd(config: FleetConfig, host: str, cmd: str, timeout: int = 10) -> subprocess.CompletedProcess:
    """Run a command on a remote device via SSH."""
    ssh = f"ssh -o ConnectTimeout=3 -o StrictHostKeyChecking=accept-new {config.ssh_user}@{host}"
    return subprocess.run(
        f"{ssh} '{cmd}'",
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _ping_device(host: str, timeout: int = 3) -> bool:
    """Check if device is reachable via ping."""
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", str(timeout), host],
            capture_output=True,
            timeout=timeout + 2,
        )
        return result.returncode == 0
    except Exception:
        return False


# ─── Fleet operations ─────────────────────────────────


@dataclass
class DeviceStatus:
    """Status information for a single device."""

    name: str
    host: str
    status: str = "unknown"  # up | down | ssh_fail | hot
    temp_c: float = 0.0
    ram_pct: int = 0
    disk_pct: int = 0
    containers: int = 0
    uptime: str = ""


def _parse_status_output(ds: DeviceStatus, stdout: str) -> None:
    """Parse pipe-delimited SSH output into DeviceStatus fields."""
    parts = stdout.strip().split("|")
    if parts[0].strip().isdigit():
        ds.temp_c = int(parts[0].strip()) / 1000
    if len(parts) > 1 and parts[1].strip().isdigit():
        ds.ram_pct = int(parts[1].strip())
    if len(parts) > 2 and parts[2].strip().isdigit():
        ds.disk_pct = int(parts[2].strip())
    if len(parts) > 3:
        ds.uptime = parts[3].strip()[:25]
    if len(parts) > 4 and parts[4].strip().isdigit():
        ds.containers = int(parts[4].strip())
    ds.status = "hot" if ds.temp_c > 70 else "up"


def check_device_status(config: FleetConfig, device: Device) -> DeviceStatus:
    """Check the status of a single device via SSH."""
    ds = DeviceStatus(name=device.name, host=device.host)

    if not _ping_device(device.host):
        ds.status = "down"
        return ds

    try:
        result = _ssh_cmd(
            config, device.host,
            'echo "'
            '$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo 0)|'
            '$(free -m 2>/dev/null | awk \'/Mem:/{printf "%.0f", $3/$2*100}\')|'
            '$(df / --output=pcent 2>/dev/null | tail -1 | tr -d \" %\")|'
            '$(uptime -p 2>/dev/null || uptime)|'
            '$(podman ps -q 2>/dev/null | wc -l)"',
        )
        if result.returncode != 0:
            ds.status = "ssh_fail"
            return ds

        _parse_status_output(ds, result.stdout)
        return ds

    except Exception:
        ds.status = "ssh_fail"
        return ds


def fleet_status(config: FleetConfig) -> list[DeviceStatus]:
    """Check status of all fleet devices (parallel)."""
    results: list[DeviceStatus] = []

    with ThreadPoolExecutor(max_workers=min(10, len(config.devices) or 1)) as ex:
        futures = {
            ex.submit(check_device_status, config, dev): name
            for name, dev in config.devices.items()
        }
        for future in as_completed(futures):
            results.append(future.result())

    return sorted(results, key=lambda d: d.name)


def print_fleet_status(statuses: list[DeviceStatus]) -> None:
    """Print fleet status as a rich table."""
    table = Table(title="Fleet Status")
    table.add_column("Name", style="cyan")
    table.add_column("IP")
    table.add_column("Status")
    table.add_column("Temp")
    table.add_column("RAM")
    table.add_column("Disk")
    table.add_column("Containers", justify="right")
    table.add_column("Uptime")

    for s in statuses:
        status_str = {
            "up": "[green]✅ UP[/]",
            "down": "[red]❌ DOWN[/]",
            "ssh_fail": "[red]❌ SSH[/]",
            "hot": "[yellow]⚠️ HOT[/]",
        }.get(s.status, s.status)

        if s.status in ("down", "ssh_fail"):
            table.add_row(s.name, s.host, status_str, "—", "—", "—", "—", "—")
        else:
            table.add_row(
                s.name, s.host, status_str,
                f"{s.temp_c:.0f}°C", f"{s.ram_pct}%", f"{s.disk_pct}%",
                str(s.containers), s.uptime,
            )

    console.print(table)
    down = sum(1 for s in statuses if s.status in ("down", "ssh_fail"))
    if down:
        console.print(f"\n[yellow]⚠  {down} device(s) unreachable![/]")


def deploy_to_device(
    config: FleetConfig, device: Device, app_name: str, tag: str = "latest"
) -> bool:
    """Deploy a single app to a single device."""
    app = config.apps.get(app_name)
    if not app:
        console.print(f"[red]Unknown app: {app_name}[/]")
        return False

    image = app.image.replace("${TAG}", tag)
    host = device.host

    console.print(f"  📡 {device.name} ({host})...")

    try:
        # Pull image
        result = _ssh_cmd(config, host, f"podman pull {image}", timeout=120)
        if result.returncode != 0:
            console.print(f"  [red]✗ Pull failed on {device.name}[/]")
            return False

        # Stop and remove old container
        _ssh_cmd(config, host, f"podman stop {app_name} 2>/dev/null; podman rm {app_name} 2>/dev/null")

        # Build run command
        ports = " ".join(f"-p {p}" for p in app.ports)
        envs = " ".join(f"-e {k}={v}" for k, v in {**app.env, **device.variables}.items())
        restart = f"--restart={app.restart}" if app.restart != "no" else ""

        run_cmd = f"podman run -d --name {app_name} {ports} {envs} {restart} {image}".strip()
        result = _ssh_cmd(config, host, run_cmd, timeout=60)

        if result.returncode != 0:
            console.print(f"  [red]✗ Run failed on {device.name}[/]")
            return False

        console.print(f"  [green]✓ {device.name}: {app_name}:{tag} running[/]")
        return True

    except Exception as e:
        console.print(f"  [red]✗ {device.name}: {e}[/]")
        return False


def deploy_to_group(
    config: FleetConfig,
    group_name: str | None = None,
    device_name: str | None = None,
    app_name: str = "",
    tag: str = "latest",
) -> bool:
    """Deploy app to a group of devices using the group's update strategy."""
    targets: list[Device] = []
    for name, dev in config.devices.items():
        if device_name and name != device_name:
            continue
        if group_name and dev.group != group_name:
            continue
        targets.append(dev)

    if not targets:
        console.print("[red]No matching devices[/]")
        return False

    strategy = "parallel"
    max_parallel = 5
    if group_name and group_name in config.groups:
        grp = config.groups[group_name]
        strategy = grp.update_strategy
        max_parallel = grp.max_parallel

    console.print(f"🚀 Deploying {app_name}:{tag} to {len(targets)} device(s) ({strategy})")

    if strategy == "rolling":
        return _deploy_rolling(config, targets, app_name, tag)
    elif strategy == "canary":
        canary_count = config.groups.get(group_name or "", DeviceGroup(name="")).canary_count
        return _deploy_canary(config, targets, app_name, tag, canary_count)
    else:
        return _deploy_parallel(config, targets, app_name, tag, max_parallel)


def _deploy_rolling(config: FleetConfig, targets: list[Device], app: str, tag: str) -> bool:
    """Deploy to devices one at a time with a pause between each."""
    all_ok = True
    for dev in targets:
        if not deploy_to_device(config, dev, app, tag):
            all_ok = False
        time.sleep(2)
    return all_ok


def _deploy_canary(
    config: FleetConfig, targets: list[Device], app: str, tag: str, canary_count: int
) -> bool:
    """Deploy to canary device(s) first, then the rest."""
    canaries = targets[:canary_count]
    rest = targets[canary_count:]

    console.print(f"  🐤 Canary: deploying to {len(canaries)} device(s) first")
    for dev in canaries:
        if not deploy_to_device(config, dev, app, tag):
            console.print("[red]Canary failed — aborting[/]")
            return False

    if rest:
        console.print(f"  ✅ Canary OK — deploying to remaining {len(rest)} device(s)")
        for dev in rest:
            deploy_to_device(config, dev, app, tag)

    return True


def _deploy_parallel(
    config: FleetConfig, targets: list[Device], app: str, tag: str, max_workers: int
) -> bool:
    """Deploy to all devices in parallel."""
    failed: list[str] = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {
            ex.submit(deploy_to_device, config, dev, app, tag): dev.name
            for dev in targets
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                if not future.result():
                    failed.append(name)
            except Exception:
                failed.append(name)

    if failed:
        console.print(f"[red]Failed on: {', '.join(failed)}[/]")
        return False
    console.print(f"[green]✓ Deployed {app}:{tag} to {len(targets)} device(s)[/]")
    return True


def add_device(
    config: FleetConfig,
    name: str,
    host: str,
    group: str = "default",
    apps: list[str] | None = None,
) -> Device:
    """Add a new device to the fleet config."""
    device = Device(
        name=name,
        host=host,
        group=group,
        apps=apps or ["monitoring-agent"],
    )
    config.devices[name] = device
    return device
