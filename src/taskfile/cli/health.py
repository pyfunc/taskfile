"""## Health check CLI commands for taskfile

Check health of deployed services and infrastructure.

### Overview

The `health` command performs runtime health checks:
- **HTTP endpoints** - Check if services respond
- **Docker containers** - Verify container status
- **SSH connectivity** - Test SSH access to remote hosts
- **Disk space** - Check available storage
- **Memory** - Verify sufficient RAM

### Usage

```bash
# Check all services
taskfile health

# Check specific environment
taskfile health --env production

# Check with timeout
taskfile health --timeout 30
```

### Health Status

| Status | Icon | Description |
|--------|------|-------------|
| `healthy` | ✅ | Service responding correctly |
| `degraded` | ⚠️ | Service working with issues |
| `unhealthy` | ❌ | Service not responding |

### Why clickmd?

Uses `clickmd` for consistent CLI experience and markdown rendering of health reports.

### Dependencies

- `clickmd` - CLI framework
- `rich` - Rich console output for status tables
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import clickmd as click

from taskfile.cli.main import console, main
from taskfile.health import health_check_all, print_health_report, run_health_checks
from taskfile.parser import TaskfileNotFoundError, TaskfileParseError, load_taskfile

if TYPE_CHECKING:
    pass


@main.command(name="health")
@click.option("--domain", help="Domain to check (overrides Taskfile config)")
@click.option("--ssh-host", help="SSH host for remote checks")
@click.option("--ssh-user", default="deploy", help="SSH user")
@click.option("--ssh-key", default="~/.ssh/id_ed25519", help="SSH key path")
@click.option("--no-ssh", is_flag=True, help="Skip SSH/remote checks")
@click.pass_context
def health_cmd(ctx, domain, ssh_host, ssh_user, ssh_key, no_ssh):
    """Check health of deployed services.

    Verifies web app, landing page, and infrastructure are responding.

    \b
    Examples:
        taskfile --env prod health
        taskfile health --domain example.com
        taskfile health --ssh-host 123.45.67.89 --ssh-user deploy
    """
    try:
        config = load_taskfile(ctx.obj.get("taskfile_path"))

        # Determine domain
        check_domain = domain
        if not check_domain:
            # Try to get from prod environment variables
            if "prod" in config.environments:
                env = config.environments["prod"]
                check_domain = env.variables.get("DOMAIN")
                if not ssh_host:
                    ssh_host = env.ssh_host

        if not check_domain:
            console.print("[red]Error:[/] No domain specified. Use --domain or set DOMAIN in .env.prod")
            sys.exit(1)

        # Run health checks
        console.print(f"[bold]Checking health of {check_domain}...[/]")

        report = run_health_checks(
            domain=check_domain,
            ssh_host=None if no_ssh else (ssh_host or check_domain),
            ssh_user=ssh_user,
            ssh_key=ssh_key,
        )

        print_health_report(report)

        if report.overall != "healthy":
            sys.exit(1)

    except (TaskfileNotFoundError, TaskfileParseError) as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)
