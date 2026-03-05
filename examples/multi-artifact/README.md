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
                    ┌── py-test ── py-build ── py-publish ───→ PyPI
                    │
test-all (parallel) ├── rs-test ── rs-build ── rs-publish ───→ crates.io
                    │                └── rs-build-cross ─────→ GitHub Releases
                    │
                    └── js-test ── js-build ── js-publish ───→ npm

                    docker-build ── docker-push ─────────────→ GHCR + Docker Hub
```

## Użycie

```bash
# Testy (3 języki parallel)
taskfile run test-all

# Lint (parallel, continue on error)
taskfile run lint-all

# Build wszystkich 4 artefaktów (parallel)
taskfile run build-all

# Publikacja do 5 rejestrów naraz (parallel)
taskfile auth setup                          # jednorazowo
taskfile run publish-all --var VERSION=1.0.0

# GitHub Release z cross-compiled binarkami
taskfile run github-release --var VERSION=1.0.0

# Deploy Docker na produkcję
taskfile --env prod run docker-deploy --var VERSION=1.0.0

# Full release: tag + lint + test
taskfile run release --var VERSION=1.0.0

# Weryfikacja — czy wszystkie artefakty dostępne
taskfile run verify --var VERSION=1.0.0
```

## Wymagane tokeny

| Rejestr | Zmienna | Setup |
|---------|---------|-------|
| PyPI | `PYPI_TOKEN` | `taskfile auth setup --registry pypi` |
| crates.io | `CARGO_TOKEN` | `taskfile auth setup --registry crates` |
| npm | `NPM_TOKEN` | `taskfile auth setup --registry npm` |
| GitHub | `GITHUB_TOKEN` | `taskfile auth setup --registry github` |
| Docker Hub | `DOCKER_TOKEN` | `taskfile auth setup --registry docker` |

Lub: `taskfile auth setup` (wszystkie naraz)

## Kluczowe cechy

- **`parallel: true`** — testy i buildy 3 języków równolegle
- **`continue_on_error: true`** — lint nie blokuje pipeline
- **Jeden `VERSION`** — wspólna wersja, override z CLI: `--var VERSION=X`
- **5 rejestrów** z jednego `taskfile run publish-all`
- **Brak zbędnych `environments`** — tylko `prod` (dla docker-deploy)
