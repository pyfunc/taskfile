# fixop — Ekstrakcja narzędzia do naprawiania zależności infrastrukturalnych

## 1. Czym jest fixop?

**fixop** = **fix** + **op**(erations) — samodzielna paczka Python odpowiedzialna za **wykrywanie i naprawianie problemów infrastrukturalnych** na serwerach zdalnych i lokalnych. Niezależna od Taskfile.yml — działa na poziomie systemu operacyjnego, kontenerów i sieci.

Kluczowa zasada: **fixop nie zna formatu Taskfile.yml**. Operuje na prymitywach infrastruktury (SSH, DNS, firewall, kontenery, systemd). Taskfile jest konsumentem fixop, nie odwrotnie.

```
┌─────────────────────────────────────────────┐
│  taskfile (CLI + runner + parser)            │
│    ├── diagnostics/checks.py    → config     │
│    ├── diagnostics/checks_ssh.py→ ← EXTRACT │
│    ├── diagnostics/checks_ports.py→←EXTRACT  │
│    ├── diagnostics/fixes.py     → mixed      │
│    └── diagnostics/llm_repair.py→ classify   │
│                                              │
│    uses: fixop.check_dns(), fixop.fix_ufw()  │
└──────────────┬──────────────────────────────┘
               │ pip install fixop
┌──────────────▼──────────────────────────────┐
│  fixop (standalone infra fix toolkit)        │
│    ├── ssh.py        — SSH transport         │
│    ├── dns.py        — DNS checks + fixes    │
│    ├── firewall.py   — UFW/iptables          │
│    ├── containers.py — Podman/Docker health  │
│    ├── systemd.py    — unit mgmt + restart   │
│    ├── tls.py        — cert validation       │
│    ├── deploy.py     — artifact validation   │
│    ├── models.py     — Issue, FixResult      │
│    └── cli.py        — standalone CLI        │
└─────────────────────────────────────────────┘
```

---

## 2. Co przenieść z taskfile → fixop

### Mapa migracji: plik → co wyciągnąć → gdzie trafi

| Plik źródłowy w taskfile | Funkcje do ekstrakcji | Cel w fixop | Uwagi |
|---|---|---|---|
| `diagnostics/checks_ssh.py` (266L) | `check_ssh_keys()`, `_test_ssh()`, `check_ssh_connectivity()`, `check_remote_health()` | `fixop/ssh.py` + `fixop/containers.py` | **Cały plik** nadaje się do ekstrakcji — 0 zależności od `TaskfileConfig` w core logic |
| `diagnostics/checks_ports.py` (157L) | `_is_port_free()`, `_find_free_port_near()`, `_who_uses_port()`, `_is_docker_process()`, `_resolve_port_conflict()` | `fixop/ports.py` | Wyciągnąć pure logic, zostawić `check_ports()` wrapper w taskfile |
| `diagnostics/checks.py` (932L) | `check_docker()`, `check_ssh_keys()`, `check_ssh_connectivity()`, `_check_registry_reachable()`, `_extract_registry_host()` | `fixop/containers.py` + `fixop/ssh.py` | Wyciągnąć ~150L infra checks, reszta (config validation) zostaje |
| `diagnostics/fixes.py` (204L) | `_fix_rename_port()`, `_fix_run_command()` | `fixop/ports.py` + `fixop/cli.py` | Tylko fixy infrastrukturalne, config fixy zostają |
| `diagnostics/llm_repair.py` (222L) | `classify_runtime_error()`, `_extract_image_name()`, `_extract_missing_binary()` | `fixop/classify.py` | Error classification jest generyczna — nie zależy od taskfile |
| `runner/ssh.py` (151L) | SSH transport layer | `fixop/ssh.py` | Reużywalna warstwa SSH |
| `runner/commands.py` (752L) | `_classify_exit_code()`, `_get_tip_for_failure()` | `fixop/classify.py` | ~40L — tips i exit code mapping |
| `cli/health.py` (70L) | `check_http_endpoint()`, `check_ssh_service()` | `fixop/health.py` | Endpoint health checks |
| `deploy_utils.py` (492L) | `_check_compose_services()` (CC=12) | `fixop/deploy.py` | Validate deploy artifacts |

### Co **NIE** przenosić (zostaje w taskfile)

| Plik | Powód |
|---|---|
| `diagnostics/checks.py` — `check_taskfile()`, `check_env_files()`, `check_unresolved_variables()`, `validate_before_run()` | Zależą od `TaskfileConfig` — specyficzne dla formatu Taskfile.yml |
| `diagnostics/report.py` | Prezentacja Rich — taskfile-specific formatting |
| `diagnostics/__init__.py` — `ProjectDiagnostics` facade | Orkiestracja checks — zależy od config loading |
| `runner/commands.py` — `execute_commands()`, `run_command()` | Task execution engine — core taskfile |
| `diagnostics/fixes.py` — `_fix_copy_env_example()`, `_fix_create_taskfile()`, `_fix_init_git()` | Config/project setup — taskfile-specific |

---

## 3. Struktura paczki fixop

```
/home/tom/github/wronai/fixop/
├── pyproject.toml
├── README.md
├── LICENSE
├── src/
│   └── fixop/
│       ├── __init__.py          # re-exports: check_*, fix_*, Issue, FixResult
│       ├── models.py            # Issue, FixResult, Severity, Category enums
│       ├── ssh.py               # SSH transport + connectivity checks
│       ├── dns.py               # DNS resolution + resolv.conf + systemd-resolved
│       ├── firewall.py          # UFW forward policy + iptables NAT masquerade
│       ├── containers.py        # Podman/Docker: health, DNS inside containers, images
│       ├── systemd.py           # Unit management, graceful restart, daemon-reload
│       ├── tls.py               # Certificate validation (Let's Encrypt, self-signed)
│       ├── ports.py             # Port conflict detection + resolution
│       ├── deploy.py            # Deploy artifact validation (unresolved vars, placeholders)
│       ├── health.py            # HTTP/TCP endpoint health checks
│       ├── classify.py          # Runtime error classification (exit codes, stderr patterns)
│       └── cli.py               # Standalone CLI: fixop check, fixop fix, fixop doctor
└── tests/
    ├── test_dns.py
    ├── test_firewall.py
    ├── test_containers.py
    ├── test_systemd.py
    ├── test_tls.py
    ├── test_ports.py
    ├── test_deploy.py
    ├── test_classify.py
    └── conftest.py              # SSH mock fixtures
```

---

## 4. Kluczowe moduły fixop — co zawierają

### `fixop/models.py` — wspólne typy

```python
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional

class Severity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class Category(Enum):
    DNS = "dns"
    FIREWALL = "firewall"
    CONTAINER = "container"
    SYSTEMD = "systemd"
    TLS = "tls"
    PORT = "port"
    SSH = "ssh"
    DEPLOY = "deploy"

class FixStrategy(Enum):
    AUTO = "auto"           # fixop can fix it without confirmation
    CONFIRM = "confirm"     # needs user confirmation
    MANUAL = "manual"       # provides instructions only
    SKIP = "skip"           # informational, no fix needed

@dataclass
class Issue:
    category: Category
    severity: Severity
    message: str
    fix_strategy: FixStrategy = FixStrategy.MANUAL
    fix_command: Optional[str] = None  # shell command to fix
    details: Optional[str] = None
    host: Optional[str] = None         # which host this applies to

@dataclass
class FixResult:
    issue: Issue
    success: bool
    output: str = ""
    error: str = ""

@dataclass
class HostContext:
    """SSH connection context for remote operations."""
    host: str
    user: str = "root"
    port: int = 22
    key: str = "~/.ssh/id_ed25519"

    @property
    def ssh_cmd(self) -> list[str]:
        return [
            "ssh", "-p", str(self.port),
            "-i", self.key,
            "-o", "StrictHostKeyChecking=accept-new",
            f"{self.user}@{self.host}",
        ]
```

### `fixop/dns.py` — z Twojego troubleshootingu DNS

```python
"""DNS diagnostics and fixes.

Covers:
- Container DNS resolution (Podman bridge → 10.89.0.1 broken)
- Host DNS resolution (systemd-resolved → 127.0.0.53 broken)
- resolv.conf generation and deployment
"""

def check_host_dns(ctx: HostContext) -> list[Issue]:
    """Check if host can resolve external domains."""
    ...

def check_container_dns(ctx: HostContext, container: str = "traefik") -> list[Issue]:
    """Check if container can resolve external domains (nslookup inside container)."""
    ...

def check_systemd_resolved(ctx: HostContext) -> list[Issue]:
    """Check if systemd-resolved is blocking DNS on 127.0.0.53."""
    ...

def fix_resolv_conf(ctx: HostContext, nameservers: list[str] = None) -> FixResult:
    """Write public DNS to /etc/resolv.conf on remote host."""
    ...

def fix_disable_systemd_resolved(ctx: HostContext) -> FixResult:
    """Stop and disable systemd-resolved, set static resolv.conf."""
    ...

def generate_container_resolv_conf(output_path: str, nameservers: list[str] = None) -> str:
    """Generate resolv.conf for mounting into containers."""
    ...
```

### `fixop/firewall.py` — UFW FORWARD fix

```python
"""Firewall diagnostics and fixes.

Covers:
- UFW DEFAULT_FORWARD_POLICY check
- iptables NAT masquerade for container networks
- Port forwarding rules
"""

def check_ufw_forward_policy(ctx: HostContext) -> list[Issue]:
    """Check if UFW blocks container forwarding (DEFAULT_FORWARD_POLICY=DROP)."""
    ...

def check_nat_masquerade(ctx: HostContext, subnet: str = "10.88.0.0/16") -> list[Issue]:
    """Check if NAT masquerade exists for container subnet."""
    ...

def fix_ufw_allow_routed(ctx: HostContext) -> FixResult:
    """Set UFW default allow routed."""
    ...

def fix_nat_masquerade(ctx: HostContext, subnet: str = "10.88.0.0/16") -> FixResult:
    """Add iptables NAT masquerade rule for container subnet."""
    ...
```

### `fixop/systemd.py` — graceful restart

```python
"""Systemd unit management with race condition prevention.

Covers:
- Graceful restart (stop → wait → verify → start)
- daemon-reload
- Unit status checks
"""

def check_unit_status(ctx: HostContext, units: list[str]) -> list[Issue]:
    """Check if systemd units are active."""
    ...

def graceful_restart(ctx: HostContext, unit: str, delay: int = 3) -> FixResult:
    """Stop → sleep → verify stopped → start (prevents port binding race)."""
    ...

def daemon_reload(ctx: HostContext) -> FixResult:
    """Run systemctl daemon-reload on remote."""
    ...
```

### `fixop/deploy.py` — walidacja deploy artifacts

```python
"""Deploy artifact validation.

Covers:
- Unresolved ${VAR} in YAML/container files
- Placeholder detection (example.com, changeme, your-*)
- File existence checks before SCP
"""

def check_unresolved_vars(paths: list[str], patterns: list[str] = None) -> list[Issue]:
    """Scan files for unresolved ${VAR} and {{VAR}} patterns."""
    ...

def check_placeholders(paths: list[str]) -> list[Issue]:
    """Detect placeholder values (example.com, changeme, your-*)."""
    ...

def check_files_exist(file_patterns: list[str], base_dir: str = ".") -> list[Issue]:
    """Verify deploy files exist before upload (pre-SCP gate)."""
    ...
```

### `fixop/tls.py` — cert validation

```python
"""TLS certificate diagnostics.

Covers:
- Let's Encrypt cert validation
- Self-signed cert detection
- ACME challenge readiness
"""

def check_certificate(domain: str, port: int = 443) -> list[Issue]:
    """Check if domain has valid TLS certificate."""
    ...

def check_acme_readiness(ctx: HostContext, container: str = "traefik") -> list[Issue]:
    """Check if ACME can resolve (DNS + port 443 open + no rate limit)."""
    ...
```

### `fixop/classify.py` — error classification

```python
"""Runtime error classification.

Extracted from taskfile's classify_runtime_error() and _classify_exit_code().
Maps exit codes + stderr patterns to categories.
"""

# Dispatch table instead of if/elif chain (CC=17 → CC=3)
EXIT_CODE_MAP: dict[int, tuple[Category, str]] = {
    1: (Category.CONTAINER, "General error"),
    2: (Category.DEPLOY, "Misuse of shell command"),
    126: (Category.DEPLOY, "Permission denied or not executable"),
    127: (Category.DEPLOY, "Command not found"),
    128: (Category.CONTAINER, "Invalid exit signal"),
    137: (Category.CONTAINER, "Container killed (OOM or SIGKILL)"),
    143: (Category.CONTAINER, "Container terminated (SIGTERM)"),
    255: (Category.SSH, "SSH connection failed"),
}

STDERR_PATTERNS: list[tuple[str, Category, str]] = [
    ("lookup.*on.*:53.*timeout", Category.DNS, "DNS resolution timeout"),
    ("dial tcp.*connection refused", Category.FIREWALL, "Connection refused"),
    ("address already in use", Category.PORT, "Port conflict"),
    ("self-signed certificate", Category.TLS, "Self-signed cert detected"),
    ("ACME.*unable to obtain", Category.TLS, "ACME cert generation failed"),
    ("permission denied", Category.SSH, "SSH permission denied"),
    ("no such image", Category.CONTAINER, "Container image not found"),
]

def classify_error(exit_code: int, stderr: str = "", cmd: str = "") -> Issue:
    """Classify runtime error by exit code and stderr patterns."""
    ...
```

---

## 5. Standalone CLI (`fixop/cli.py`)

fixop działa też samodzielnie (bez taskfile):

```bash
# Zainstaluj
pip install fixop

# Sprawdź zdalny serwer
fixop check --host c2006.mask.services --user root

# Sprawdź konkretne kategorie
fixop check --host c2006.mask.services --category dns,firewall,tls

# Napraw automatycznie co się da
fixop fix --host c2006.mask.services --auto

# Napraw interaktywnie (potwierdź każdy fix)
fixop fix --host c2006.mask.services --interactive

# Waliduj deploy artifacts lokalnie
fixop validate deploy/

# Sprawdź certyfikaty
fixop check-tls c2006.mask.services c2007.mask.services

# JSON output (dla CI)
fixop check --host c2006.mask.services --format json
```

---

## 6. pyproject.toml dla fixop

```toml
[project]
name = "fixop"
version = "0.1.0"
description = "Infrastructure fix operations — detect and repair DNS, firewall, containers, TLS, systemd issues"
readme = "README.md"
license = { text = "Apache-2.0" }
requires-python = ">=3.10"
authors = [{ name = "Tom Sapletta", email = "tom@sapletta.com" }]
keywords = ["infrastructure", "devops", "diagnostics", "podman", "docker", "dns", "firewall", "systemd"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Topic :: System :: Systems Administration",
    "Topic :: System :: Networking",
]
dependencies = []  # zero dependencies — uses only stdlib (subprocess, socket, ssl, pathlib)

[project.optional-dependencies]
dev = ["pytest", "pytest-cov", "ruff"]
ssh = ["paramiko"]  # optional: native SSH instead of subprocess

[project.scripts]
fixop = "fixop.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

**Zero dependencies** — fixop korzysta wyłącznie z stdlib (`subprocess`, `socket`, `ssl`, `pathlib`, `re`, `json`). SSH przez subprocess (`ssh` command), nie przez paramiko (opcjonalny extra).

---

## 7. Integracja: jak taskfile reużywa fixop

### 7.1 Dodaj fixop jako dependency

W `taskfile/pyproject.toml`:

```toml
[project]
dependencies = [
    "fixop>=0.1.0",
    # ... existing deps
]
```

### 7.2 Zamień diagnostics/checks_ssh.py na wrapper

**Przed** (w `taskfile/diagnostics/checks_ssh.py`, 266L):

```python
def check_remote_health(config):
    """Complex 266-line function checking SSH, containers, disk, memory..."""
    issues = []
    for env_name, env in config.environments.items():
        if not env.ssh_host:
            continue
        # ... 250 lines of SSH subprocess calls
    return issues
```

**Po** (thin wrapper, ~40L):

```python
from fixop import HostContext, check_host_dns, check_container_dns,
    check_ufw_forward_policy, check_unit_status, check_certificate
from fixop.models import Issue as FixopIssue
from taskfile.diagnostics.models import Issue as TaskfileIssue

def _to_taskfile_issue(fixop_issue: FixopIssue) -> TaskfileIssue:
    """Convert fixop Issue to taskfile Issue (adapter pattern)."""
    return TaskfileIssue(
        category=_map_category(fixop_issue.category),
        severity=fixop_issue.severity.value,
        message=fixop_issue.message,
        fix=fixop_issue.fix_command,
    )

def check_remote_health(config) -> list[TaskfileIssue]:
    """Check remote server health using fixop."""
    issues = []
    for env_name, env in config.environments.items():
        if not env.ssh_host:
            continue
        ctx = HostContext(
            host=env.ssh_host,
            user=env.ssh_user or "deploy",
            port=env.ssh_port or 22,
            key=env.ssh_key or "~/.ssh/id_ed25519",
        )
        # One-liner per check instead of 50+ lines each
        issues += [_to_taskfile_issue(i) for i in check_host_dns(ctx)]
        issues += [_to_taskfile_issue(i) for i in check_container_dns(ctx)]
        issues += [_to_taskfile_issue(i) for i in check_ufw_forward_policy(ctx)]
        issues += [_to_taskfile_issue(i) for i in check_unit_status(ctx, ["traefik", "web", "landing"])]
    return issues
```

### 7.3 Zamień deploy validation

**Przed** (rozproszone w `diagnostics/checks.py`, `runner/commands.py`, `deploy_utils.py`):

```python
# 3 różne pliki, 3 różne sposoby walidacji deploy files
```

**Po** (w `taskfile/diagnostics/checks.py`):

```python
from fixop import check_unresolved_vars, check_placeholders, check_files_exist

def _check_deploy_artifacts(config, taskfile_dir):
    """Validate deploy files before upload."""
    deploy_dir = Path(taskfile_dir) / "deploy"
    if not deploy_dir.exists():
        return []
    
    files = list(deploy_dir.rglob("*.yml")) + list(deploy_dir.rglob("*.container"))
    issues = check_unresolved_vars([str(f) for f in files])
    issues += check_placeholders([str(f) for f in files])
    return [_to_taskfile_issue(i) for i in issues]
```

### 7.4 Graceful restart w deploy recipe

**Przed** (w Taskfile.yml):

```yaml
restart:
  cmds:
    - "@remote systemctl restart traefik web landing"  # race condition!
```

**Po** (taskfile generuje poprawny restart):

```python
# W taskfile/deploy_recipes.py
from fixop import graceful_restart, HostContext

def _generate_restart_commands(services, ctx):
    """Generate graceful restart sequence."""
    for svc in services:
        result = graceful_restart(ctx, svc, delay=3)
        if not result.success:
            raise TaskRunError(f"Restart failed: {result.error}")
```

### 7.5 Dodaj fixop checks do `taskfile doctor`

W `taskfile/cli/interactive/wizards.py`:

```python
# W funkcji doctor() — dodaj nową warstwę
def doctor(...):
    ...
    if remote:
        # Layer: fixop infra checks (NEW)
        try:
            from fixop import check_host_dns, check_container_dns, 
                check_ufw_forward_policy, check_certificate
            # Uruchom fixop checks i skonwertuj wyniki
            ...
        except ImportError:
            print("  ℹ Install fixop for deeper infra checks: pip install fixop")
```

---

## 8. Kolejność implementacji

### Sprint 1 (tydzień 1): Core fixop

```bash
# 1. Zainicjuj repo
mkdir -p /home/tom/github/wronai/fixop/src/fixop
cd /home/tom/github/wronai/fixop

# 2. Stwórz pliki
# models.py → Issue, FixResult, HostContext (nowe, nie kopiuj z taskfile)
# ssh.py    ← wyciągnij z taskfile/runner/ssh.py (151L) + checks_ssh.py._test_ssh()
# dns.py    ← NOWE — z troubleshooting notes (resolv.conf, systemd-resolved, container DNS)
# firewall.py ← NOWE — z troubleshooting notes (UFW forward, NAT masquerade)
# containers.py ← wyciągnij z checks_ssh.py.check_remote_health() + checks.py.check_docker()

# 3. Testy
# test_dns.py, test_firewall.py — mockowane SSH (subprocess)
```

### Sprint 2 (tydzień 2): Extended checks + CLI

```bash
# systemd.py  ← NOWE — graceful_restart pattern
# tls.py      ← NOWE — z troubleshooting notes (Let's Encrypt, ACME readiness)
# ports.py    ← wyciągnij z checks_ports.py (157L — prawie cały plik)
# deploy.py   ← NOWE — unresolved vars scanner
# classify.py ← wyciągnij z llm_repair.py.classify_runtime_error() + commands.py._classify_exit_code()
# cli.py      ← NOWE — standalone CLI

# Publish: pip install fixop
```

### Sprint 3 (tydzień 3): Integracja z taskfile

```bash
# 1. Dodaj fixop do taskfile/pyproject.toml dependencies
# 2. Zamień checks_ssh.py na thin wrapper → fixop
# 3. Zamień checks_ports.py na thin wrapper → fixop
# 4. Dodaj fixop checks do doctor --remote
# 5. Dodaj deploy artifact validation do pre-deploy gate
# 6. Backward compat testy
```

---

## 9. Podsumowanie — co zyskujesz

| Aspekt | Przed (wszystko w taskfile) | Po (fixop wydzielony) |
|---|---|---|
| **Reużywalność** | Checks przywiązane do TaskfileConfig | fixop działa z dowolnym narzędziem (Ansible, make, ręcznie) |
| **Testowalność** | Testy wymagają full taskfile setup | fixop testuje SSH mock + pure functions |
| **CC complexity** | `check_remote_health` CC=15, `classify_runtime_error` CC=17 | Dispatch tables CC≤5, single-purpose functions CC≤8 |
| **checks_ssh.py** | 266L monolith | ~40L wrapper + fixop |
| **Nowe checks** | Trzeba modyfikować taskfile | Dodaj check w fixop → taskfile dostaje automatycznie |
| **Standalone** | Wymaga `pip install taskfile` do diagnozy | `fixop check --host server` — zero config |
| **Doctor warnings** | 3 warnings (`${COMPOSE}` not found) | fixop oddziela infra od config issues |

Najważniejsze: **każdy problem z Twoich logów** (DNS timeout → `10.89.0.1:53`, UFW FORWARD DROP, systemd-resolved blocking, self-signed cert, race condition restart) staje się **jednolinijkowym wywołaniem fixop** zamiast 30-50 linii ręcznego troubleshootingu.
