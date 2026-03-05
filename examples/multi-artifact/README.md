# Multi-Artifact — Python + Rust + Node.js + Docker

Monorepo generujące **4 artefakty** z jednego folderu, publikowane do 5 rejestrów.

## Scenariusz

Projekt `unirepo` to API z SDK w trzech językach:

```
┌──────────────────────────────────────────────────────────────┐
│  unirepo/                                                    │
│                                                              │
│  packages/python-sdk/  →  PyPI          (pip install)        │
│  packages/rust-cli/    →  crates.io     (cargo install)      │
│                        →  GitHub Rel.   (binaries download)  │
│  packages/node-sdk/    →  npm           (npm install)        │
│  Dockerfile            →  GHCR          (docker pull)        │
│                        →  Docker Hub    (docker pull)        │
└──────────────────────────────────────────────────────────────┘
```

## Struktura projektu

```
multi-artifact/
├── Taskfile.yml               # Unified pipeline for all artifacts
├── Dockerfile                 # API server image
├── docker-compose.yml         # Local dev
├── packages/
│   ├── python-sdk/
│   │   ├── pyproject.toml
│   │   ├── src/unirepo_sdk/
│   │   │   └── __init__.py
│   │   └── tests/
│   ├── rust-cli/
│   │   ├── Cargo.toml
│   │   ├── src/
│   │   │   └── main.rs
│   │   └── tests/
│   └── node-sdk/
│       ├── package.json
│       ├── tsconfig.json
│       ├── src/
│       │   └── index.ts
│       └── tests/
└── README.md
```

## Pipeline

```
                    ┌── py-test ── py-build ── py-publish ──→ PyPI
                    │
test-all (parallel) ├── rs-test ── rs-build ── rs-publish ──→ crates.io
                    │                    └── rs-build-all ──→ GitHub Releases
                    │
                    └── js-test ── js-build ── js-publish ──→ npm
                    
                    docker-build ── docker-push ───────────→ GHCR + Docker Hub
```

## Użycie

### Testowanie

```bash
# Testy wszystkich trzech języków (parallel)
taskfile run test-all

# Testy jednego języka
taskfile run py-test
taskfile run rs-test
taskfile run js-test

# Linting (parallel, continue on error)
taskfile run lint-all
```

### Budowanie

```bash
# Build wszystkich 4 artefaktów (parallel)
taskfile run build-all

# Build pojedynczego artefaktu
taskfile run py-build
taskfile run rs-build
taskfile run js-build
taskfile run docker-build

# Rust CLI — cross-compile na 3 platformy
taskfile run rs-build-all
```

### Publikacja

```bash
# Konfiguracja tokenów dla wszystkich rejestrów
taskfile auth setup

# Publikacja WSZYSTKIEGO naraz (parallel)
taskfile run publish-all --var VERSION=1.0.0

# Publikacja pojedynczego artefaktu
taskfile run py-publish --var VERSION=1.0.0      # → PyPI
taskfile run rs-publish --var VERSION=1.0.0      # → crates.io
taskfile run js-publish --var VERSION=1.0.0      # → npm
taskfile run docker-push --var VERSION=1.0.0     # → GHCR + Docker Hub

# GitHub Release z binarkami
taskfile run github-release --var VERSION=1.0.0

# Deploy Docker na produkcję
taskfile --env prod run docker-deploy --var VERSION=1.0.0
```

### Full Release

```bash
# Jeden command — tag, build, publish wszystko
taskfile run release --var VERSION=1.0.0

# Następnie publish + GitHub Release:
taskfile run publish-all --var VERSION=1.0.0
taskfile run github-release --var VERSION=1.0.0

# Weryfikacja — czy wszystkie artefakty dostępne
taskfile run verify --var VERSION=1.0.0
```

### Lokalne Dev

```bash
# Start API lokalnie
taskfile run dev

# Stop
taskfile run dev-stop
```

## Wymagane tokeny

| Rejestr | Zmienna | Komenda setup |
|---------|---------|---------------|
| PyPI | `PYPI_TOKEN` | `taskfile auth setup --registry pypi` |
| crates.io | `CARGO_TOKEN` | `taskfile auth setup --registry crates` |
| npm | `NPM_TOKEN` | `taskfile auth setup --registry npm` |
| GitHub | `GITHUB_TOKEN` | `taskfile auth setup --registry github` |
| Docker Hub | `DOCKER_TOKEN` | `taskfile auth setup --registry docker` |

Lub wszystkie naraz:

```bash
taskfile auth setup
taskfile auth verify
```

## Kluczowe cechy

- **`parallel: true`** — testy i buildy trzech języków uruchamiane równolegle
- **`continue_on_error: true`** — lint nie blokuje pipeline'u
- **Jeden `VERSION`** — wspólna wersja dla wszystkich artefaktów
- **`--var VERSION=X`** — override z CLI, bez edycji pliku
- **5 rejestrów** z jednego `taskfile run publish-all`
