"""ErrorPresenter — contextual error messages with diagnosis and fix suggestions.

Formats runtime errors with:
- Clear error summary (command, exit code, first line of stderr)
- Diagnosis panel with category, root cause analysis, fix steps
- Educational 'teach' note explaining the underlying principle
- Reference to `taskfile doctor` for full diagnostics
"""

from __future__ import annotations

import re
import shutil

from rich.console import Console
from rich.panel import Panel

from taskfile.diagnostics.llm_repair import classify_runtime_error
from taskfile.diagnostics.models import (
    CATEGORY_LABELS,
    Issue,
    IssueCategory,
)

console = Console()


# ─── Install hints for common binaries ────────────────────────────────────

INSTALL_HINTS: dict[str, str] = {
    "docker": "https://docs.docker.com/get-docker/",
    "docker-compose": "pip install docker-compose  OR  use 'docker compose' (v2)",
    "podman": "sudo apt install podman",
    "ssh": "sudo apt install openssh-client",
    "scp": "sudo apt install openssh-client",
    "rsync": "sudo apt install rsync",
    "git": "sudo apt install git",
    "npm": "https://nodejs.org/",
    "node": "https://nodejs.org/",
    "cargo": "https://rustup.rs/",
    "python3": "sudo apt install python3",
    "python": "sudo apt install python3",
    "pip": "sudo apt install python3-pip",
    "curl": "sudo apt install curl",
    "wget": "sudo apt install wget",
    "jq": "sudo apt install jq",
    "make": "sudo apt install build-essential",
    "systemctl": "systemd is required (not available in containers)",
}

# ─── Placeholder detection patterns ──────────────────────────────────────

_PLACEHOLDER_WORDS = [
    "example.com",
    "your-",
    "xxx",
    "changeme",
    "replace-me",
    "replace_me",
    "todo",
    "placeholder",
    "0.0.0.0",
]


class ErrorPresenter:
    """Formats runtime errors with context, diagnosis, and fix suggestions."""

    def present(
        self,
        cmd: str,
        exit_code: int,
        stderr: str,
        task_name: str,
        env_name: str,
        variables: dict[str, str],
    ) -> None:
        """Present a rich error diagnosis after a command failure."""
        issue = classify_runtime_error(exit_code, stderr, cmd)

        console.print(f"\n[red bold]❌ Task '{task_name}' failed[/]\n")
        console.print(f"  [dim]Komenda:[/]   {cmd[:120]}")
        console.print(f"  [dim]Exit code:[/] {exit_code}")
        first_err = self._first_meaningful_line(stderr)
        if first_err:
            console.print(f"  [red]Błąd:[/]     {first_err}")
        console.print()

        # Build and display diagnosis panel
        diagnosis = self._build_diagnosis(issue, cmd, stderr, env_name, variables)
        console.print(
            Panel(
                diagnosis,
                title="[yellow bold]Diagnoza[/]",
                border_style="yellow",
                padding=(1, 2),
            )
        )

    def _build_diagnosis(
        self,
        issue: Issue,
        cmd: str,
        stderr: str,
        env_name: str,
        variables: dict[str, str],
    ) -> str:
        """Build diagnosis text with category, specifics, and fix steps."""
        lines: list[str] = []
        cat_label = CATEGORY_LABELS.get(issue.category, issue.category.value)
        lines.append(f"[bold]Kategoria:[/]  {cat_label}")
        lines.append("")

        stderr_lower = stderr.lower()

        # ── Specific diagnosis per error type ──

        if (
            "could not resolve hostname" in stderr_lower
            or "name or service not known" in stderr_lower
        ):
            lines.extend(self._diagnose_hostname(stderr, variables))

        elif (
            "command not found" in stderr_lower
            or issue.category == IssueCategory.DEPENDENCY_MISSING
        ):
            lines.extend(self._diagnose_command_not_found(stderr, cmd))

        elif "permission denied" in stderr_lower:
            lines.extend(self._diagnose_permission_denied(cmd, env_name))

        elif "connection refused" in stderr_lower:
            lines.append("Serwer odrzucił połączenie.")
            lines.append("Sprawdź czy serwis nasłuchuje na docelowym porcie.")
            lines.append("")
            lines.append("[bold]Napraw:[/]")
            lines.append("  1. Sprawdź czy serwis jest uruchomiony")
            lines.append("  2. Sprawdź firewall: [cyan]sudo ufw status[/]")

        elif "connection timed out" in stderr_lower or "operation timed out" in stderr_lower:
            lines.append("Połączenie wygasło — host nieosiągalny lub firewall blokuje.")
            lines.append("")
            lines.append("[bold]Napraw:[/]")
            lines.append("  1. Sprawdź czy host jest online: [cyan]ping <host>[/]")
            lines.append("  2. Sprawdź SSH: [cyan]taskfile fleet status[/]")

        elif "no such file or directory" in stderr_lower:
            lines.extend(self._diagnose_file_not_found(cmd, stderr))

        elif "address already in use" in stderr_lower:
            lines.append("Port jest już zajęty przez inny proces.")
            lines.append("")
            lines.append("[bold]Napraw:[/]")
            lines.append("  1. Znajdź proces: [cyan]lsof -i :<port>[/]")
            lines.append("  2. Zatrzymaj go: [cyan]docker stop <name>[/]  lub  [cyan]kill <pid>[/]")
            lines.append("  3. Lub zmień port w Taskfile.yml / docker-compose.yml")

        else:
            # Generic diagnosis
            if issue.fix_description:
                lines.append(issue.fix_description)
            else:
                lines.append(
                    f"Komenda zwróciła kod {issue.context.get('exit_code', '?') if issue.context else '?'}."
                )
                lines.append("Sprawdź output powyżej.")

        # ── Footer ──
        lines.append("")
        lines.append("[dim]Wskazówka: [cyan]taskfile doctor[/] — pełna diagnostyka[/]")

        return "\n".join(lines)

    # ─── Specific diagnosers ─────────────────────────────────────────────

    def _diagnose_hostname(self, stderr: str, variables: dict[str, str]) -> list[str]:
        """Diagnose hostname resolution failures — detect placeholders."""
        lines: list[str] = []
        host = self._extract_hostname(stderr)
        if host:
            var = self._find_variable_for_value(host, variables)
            if var and self._looks_like_placeholder(host):
                lines.append(f'Zmienna [bold]{var}[/] ma wartość [yellow]"{host}"[/]')
                lines.append("— to wygląda na placeholder.")
                lines.append("")
                lines.append("[bold]Napraw:[/]")
                lines.append("  1. Ustaw prawdziwy adres:")
                lines.append(f"     [cyan]export {var}=<prawdziwy-adres>[/]")
                lines.append("  2. Lub zapisz w .env:")
                lines.append(f'     [cyan]echo "{var}=<adres>" >> .env[/]')
            else:
                lines.append(f"Host [yellow]{host}[/] nie został rozwiązany (DNS).")
                lines.append("")
                lines.append("[bold]Napraw:[/]")
                lines.append(f"  1. Sprawdź adres: [cyan]ping {host}[/]")
                lines.append("  2. Sprawdź zmienne w Taskfile.yml i .env")
        return lines

    def _diagnose_command_not_found(self, stderr: str, cmd: str) -> list[str]:
        """Diagnose missing binary — suggest installation."""
        lines: list[str] = []
        binary = self._extract_missing_binary(stderr) or self._first_word(cmd)
        lines.append(f'Komenda [yellow]"{binary}"[/] nie jest zainstalowana.')
        install = INSTALL_HINTS.get(binary)
        if install:
            lines.append("")
            lines.append(f"[bold]Instalacja:[/]  [cyan]{install}[/]")
        elif shutil.which("apt"):
            lines.append("")
            lines.append(f"[bold]Spróbuj:[/]  [cyan]sudo apt install {binary}[/]")
        lines.append("")
        lines.append("[dim]Sprawdź: [cyan]taskfile doctor[/] → Layer 1: Preflight[/]")
        return lines

    def _diagnose_permission_denied(self, cmd: str, env_name: str) -> list[str]:
        """Diagnose permission denied errors."""
        lines: list[str] = []
        lines.append("Brak uprawnień do wykonania komendy.")
        lines.append("")
        if "@remote" in cmd or "@ssh" in cmd:
            lines.append("Na serwerze zdalnym sprawdź uprawnienia usera.")
            lines.append(f"[bold]Napraw:[/]  Sprawdź SSH user w env '{env_name}'")
        else:
            first = self._first_word(cmd)
            lines.append("[bold]Napraw:[/]")
            lines.append(f"  [cyan]chmod +x {first}[/]")
        return lines

    def _diagnose_file_not_found(self, cmd: str, stderr: str) -> list[str]:
        """Diagnose 'No such file or directory' errors."""
        lines: list[str] = []
        lines.append("Plik lub katalog nie istnieje.")
        lines.append("")
        lines.append("[bold]Napraw:[/]")
        lines.append("  1. Sprawdź ścieżki w komendzie")
        lines.append("  2. Utwórz brakujące pliki/katalogi")
        lines.append("  3. [cyan]taskfile doctor --fix[/] — automatyczne tworzenie")
        return lines

    # ─── Utility methods ─────────────────────────────────────────────────

    @staticmethod
    def _first_meaningful_line(stderr: str) -> str:
        """Extract first non-empty, non-debug line from stderr."""
        for line in stderr.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("debug") and not stripped.startswith("#"):
                return stripped[:200]
        return ""

    @staticmethod
    def _extract_hostname(stderr: str) -> str | None:
        """Extract hostname from 'Could not resolve hostname X' style errors."""
        patterns = [
            r"[Cc]ould not resolve hostname[:\s]+([^\s:]+)",
            r"Name or service not known.*?'([^']+)'",
            r"getaddrinfo.*?'([^']+)'",
        ]
        for pat in patterns:
            m = re.search(pat, stderr)
            if m:
                return m.group(1).strip("'\"")
        return None

    @staticmethod
    def _extract_missing_binary(stderr: str) -> str | None:
        """Extract binary name from 'command not found' stderr."""
        for line in stderr.splitlines():
            if "command not found" in line.lower():
                parts = line.split(":")
                if len(parts) >= 2:
                    return parts[-2].strip()
        return None

    @staticmethod
    def _find_variable_for_value(value: str, variables: dict[str, str]) -> str | None:
        """Find which variable holds a given value."""
        for k, v in variables.items():
            if value in str(v):
                return k
        return None

    @staticmethod
    def _looks_like_placeholder(value: str) -> bool:
        """Detect placeholder values: example.com, your-*, xxx, changeme."""
        return any(p in value.lower() for p in _PLACEHOLDER_WORDS)

    @staticmethod
    def _first_word(cmd: str) -> str:
        """Extract first word from command, skipping @prefixes."""
        stripped = cmd.strip()
        for prefix in ("@remote ", "@local ", "@ssh ", "@fn ", "@python "):
            if stripped.startswith(prefix):
                stripped = stripped[len(prefix) :]
                break
        return stripped.split()[0] if stripped.split() else "unknown"
