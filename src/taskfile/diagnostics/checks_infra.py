"""Local infrastructure checks — UFW firewall and container DNS.

These checks run locally (not over SSH) and detect networking issues
that cause container failures on the host machine.

When fixop is available, delegates to fixop.firewall / fixop.dns.
Otherwise uses inline implementations as fallback.
"""

from __future__ import annotations

import shutil
import socket
import subprocess
from pathlib import Path

from taskfile.diagnostics.models import (
    Issue,
    IssueCategory,
    FixStrategy,
    SEVERITY_WARNING,
    SEVERITY_INFO,
)
from taskfile.diagnostics.fixop_adapter import HAS_FIXOP

try:
    from fixop.firewall import check_ufw_forward_policy as _fixop_check_ufw
    from fixop.dns import check_container_dns as _fixop_check_container_dns
except ImportError:
    pass


def check_ufw_forward_policy() -> list[Issue]:
    """Check if UFW default FORWARD policy allows container traffic.

    When UFW is active with FORWARD=DROP (default), containers cannot
    reach the internet or each other across networks. This is the #1
    cause of 'podman pull' failures on fresh VPS setups.
    """
    if HAS_FIXOP:
        from taskfile.diagnostics.fixop_adapter import adapt_issues

        return adapt_issues(_fixop_check_ufw())

    issues: list[Issue] = []

    # Only relevant if ufw is installed
    if not shutil.which("ufw"):
        return issues

    # Check if ufw is active
    try:
        result = subprocess.run(
            ["ufw", "status"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if "inactive" in result.stdout.lower():
            return issues
    except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
        return issues

    # Check /etc/default/ufw for DEFAULT_FORWARD_POLICY
    ufw_defaults = Path("/etc/default/ufw")
    if not ufw_defaults.exists():
        return issues

    try:
        content = ufw_defaults.read_text()
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("DEFAULT_FORWARD_POLICY") and "=" in stripped:
                policy = stripped.split("=", 1)[1].strip().strip('"').strip("'")
                if policy.upper() == "DROP":
                    issues.append(
                        Issue(
                            category=IssueCategory.EXTERNAL_ERROR,
                            message="UFW DEFAULT_FORWARD_POLICY=DROP — containers cannot reach the internet",
                            severity=SEVERITY_WARNING,
                            fix_strategy=FixStrategy.MANUAL,
                            fix_description=(
                                'Set DEFAULT_FORWARD_POLICY="ACCEPT" in /etc/default/ufw, '
                                "then run: sudo ufw reload"
                            ),
                            teach=(
                                "UFW's default FORWARD policy blocks traffic between container "
                                "networks and the host. Podman and Docker containers need FORWARD=ACCEPT "
                                "to pull images, resolve DNS, and communicate across networks. "
                                "This is the most common cause of 'podman pull' timeouts on fresh VPS setups."
                            ),
                            layer=3,
                        )
                    )
                break
    except OSError:
        pass

    return issues


def check_container_dns() -> list[Issue]:
    """Check if Podman's default bridge DNS (10.88.0.1) can resolve external domains.

    Podman uses 10.88.0.1 as the DNS server on its default bridge network.
    If this resolver cannot reach upstream DNS, containers fail to pull
    images or reach ACME servers for TLS certificates.
    """
    if HAS_FIXOP:
        from taskfile.diagnostics.fixop_adapter import adapt_issues

        return adapt_issues(_fixop_check_container_dns())

    issues: list[Issue] = []

    # Only check if podman is installed
    if not shutil.which("podman"):
        return issues

    # Quick check: can we resolve via the Podman bridge DNS?
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2)
        # Try connecting to Podman's default bridge DNS
        sock.connect(("10.88.0.1", 53))
        sock.close()
    except (OSError, socket.timeout):
        # 10.88.0.1 not reachable — podman network may not be initialized yet, skip
        return issues

    # If the bridge DNS exists, verify it can resolve an external domain
    try:
        import struct

        # Build a minimal DNS query for "dns.google" (type A)
        query = (
            b"\xaa\xbb"  # Transaction ID
            b"\x01\x00"  # Flags: standard query
            b"\x00\x01"  # Questions: 1
            b"\x00\x00\x00\x00\x00\x00"  # No answers/authority/additional
            b"\x03dns\x06google\x00"  # dns.google
            b"\x00\x01"  # Type A
            b"\x00\x01"  # Class IN
        )
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(3)
        sock.sendto(query, ("10.88.0.1", 53))
        data, _ = sock.recvfrom(512)
        sock.close()

        # Check if we got a valid response (RCODE == 0 in flags)
        if len(data) >= 4:
            flags = struct.unpack("!H", data[2:4])[0]
            rcode = flags & 0x0F
            if rcode != 0:
                issues.append(
                    Issue(
                        category=IssueCategory.EXTERNAL_ERROR,
                        message="Podman bridge DNS (10.88.0.1) cannot resolve external domains",
                        severity=SEVERITY_WARNING,
                        fix_strategy=FixStrategy.MANUAL,
                        fix_description=(
                            "Mount a custom resolv.conf with public DNS servers into containers. "
                            "Run: taskfile quadlet generate (auto-generates resolv.conf with 8.8.8.8/1.1.1.1)"
                        ),
                        teach=(
                            "Podman's default bridge network uses 10.88.0.1 as DNS resolver. "
                            "If this resolver can't reach upstream DNS (e.g., due to UFW or network config), "
                            "containers fail to pull images or reach external services. "
                            "The fix is to mount a resolv.conf with public DNS servers (8.8.8.8, 1.1.1.1) "
                            "into each container via Volume=./resolv.conf:/etc/resolv.conf:ro."
                        ),
                        layer=3,
                    )
                )
    except (OSError, socket.timeout):
        issues.append(
            Issue(
                category=IssueCategory.EXTERNAL_ERROR,
                message="Podman bridge DNS (10.88.0.1) not responding — container DNS may be broken",
                severity=SEVERITY_INFO,
                fix_strategy=FixStrategy.MANUAL,
                fix_description=(
                    "Ensure Podman network is initialized (podman network ls) and "
                    "mount a custom resolv.conf for reliable DNS"
                ),
                layer=3,
            )
        )

    return issues
