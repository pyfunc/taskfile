# Script Extraction — Split Taskfile into Shell/Python Scripts

Jak rozbić Taskfile.yml na osobne skrypty dla złożonej logiki.

## Zasada

```
Taskfile.yml = deklaratywna konfiguracja (CO)
scripts/     = imperatywna logika (JAK)
```

**Kiedy wyciągać do skryptu:**
- Logika > 3 linii
- Warunki / pętle / retry
- Operacje wymagające Pythona (JSON, API, SSH)
- Reużywalne między projektami

**Kiedy zostawiać inline:**
- Proste jednolinijkowe komendy
- `@remote` SSH commands (obsługiwane przez taskfile)
- Standardowe narzędzia (pytest, ruff, docker build)

## Struktura

```
project/
├── Taskfile.yml              # Deklaratywna konfiguracja
├── scripts/
│   ├── build.sh              # Shell: złożony build z cache + labels
│   ├── deploy.sh             # Shell: deploy switch per environment
│   ├── health-check.sh       # Shell: health check z retries
│   ├── ci-pipeline.sh        # Shell: pełny CI pipeline
│   ├── release.py            # Python: tag + build + push workflow
│   ├── migrate.py            # Python: database migration
│   ├── report.py             # Python: deployment report (JSON)
│   └── provision.py          # Python: SSH provisioning logic
└── README.md
```

## Jak to działa

Taskfile runner **automatycznie** przekazuje wszystkie zmienne (`${IMAGE}`, `${TAG}`, `${ENV}`, etc.) jako zmienne środowiskowe do skryptów:

```yaml
# Taskfile.yml — deklaratywne "CO"
tasks:
  build:
    cmds:
      - ./scripts/build.sh          # ${IMAGE}, ${TAG} dostępne w skrypcie
  release:
    cmds:
      - python scripts/release.py --tag ${TAG}   # CLI arg + env vars
```

```bash
# scripts/build.sh — imperatywne "JAK"
#!/usr/bin/env bash
set -euo pipefail
docker build -t "${IMAGE}:${TAG}" .    # ${IMAGE}, ${TAG} z taskfile
```

## Usage

```bash
# Proste taski (inline w Taskfile)
taskfile run test
taskfile run lint

# Złożone taski (delegowane do skryptów)
taskfile run build --var TAG=v1.0.0
taskfile run release --var TAG=v1.0.0
taskfile run deploy --env prod

# Python skrypty
taskfile run migrate --env prod
taskfile run report --env prod

# CI pipeline (mix inline + skrypt)
taskfile run ci
```

## Wzorce ekstrakcji

### 1. Shell script — prosta logika z retry/warunkami

```yaml
# Taskfile.yml
tasks:
  health:
    cmds: [./scripts/health-check.sh]
```

```bash
# scripts/health-check.sh
for i in $(seq 1 5); do
    curl -sf "https://${DOMAIN}/health" && exit 0
    sleep 3
done
exit 1
```

### 2. Python script — złożona logika, JSON, API

```yaml
# Taskfile.yml
tasks:
  release:
    cmds: [python scripts/release.py --tag ${TAG}]
```

```python
# scripts/release.py
import os, subprocess
image = os.environ["IMAGE"]  # z taskfile runner
tag = args.tag                # z CLI
subprocess.run(f"docker build -t {image}:{tag} .", shell=True, check=True)
```

### 3. Mix — inline setup + script logic

```yaml
# Taskfile.yml
tasks:
  ci:
    cmds:
      - pip install -e ".[dev]"       # inline: prosty setup
      - ./scripts/ci-pipeline.sh      # script: złożony pipeline
```
