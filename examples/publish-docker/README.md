# Publish Docker — Container Image

Publikacja obrazu Docker na GHCR + Docker Hub za pomocą Taskfile.

## Struktura projektu

```
publish-docker/
├── Taskfile.yml          # Pipeline: build → push → deploy
├── Dockerfile            # Obraz aplikacji
├── docker-compose.yml    # Lokalne dev
└── README.md
```

## Pipeline

```
lint-dockerfile ── build ──┬── push-ghcr ────┬── deploy
                           └── push-dockerhub┘
                    (lub build-multiarch → oba naraz)
```

## Użycie

```bash
# Login do rejestrów
taskfile run login-ghcr
taskfile run login-dockerhub

# Build lokalny
taskfile run build --var TAG=v1.0.0

# Push na GHCR
taskfile run push-ghcr --var TAG=v1.0.0

# Push na Docker Hub
taskfile run push-dockerhub --var TAG=v1.0.0

# Push na oba rejestry (parallel)
taskfile run push-all --var TAG=v1.0.0

# Build multi-arch (amd64 + arm64) + push
taskfile run build-multiarch --var TAG=v1.0.0

# Deploy na produkcję
taskfile --env prod run deploy --var TAG=v1.0.0

# Skan bezpieczeństwa
taskfile run scan --var TAG=v1.0.0

# Pełny release
taskfile run release --var TAG=v1.0.0
```

## Wymagane tokeny

| Zmienna | Gdzie uzyskać |
|---------|---------------|
| `GITHUB_TOKEN` | https://github.com/settings/tokens (scope: `write:packages`) |
| `DOCKER_TOKEN` | https://hub.docker.com/settings/security |

```bash
taskfile auth setup --registry github
taskfile auth setup --registry docker
```
