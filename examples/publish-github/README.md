# Publish GitHub — GitHub Releases

Publikacja cross-compiled Go binarek na GitHub Releases.

## Taskfile.yml — 75 linii

```
build-linux ──┐
build-macos ──┤── (parallel) ── build-all (+ checksums) ── release (gh release create)
build-windows ┘
```

**Brak sekcji `environments`** — nie potrzebna. Jedno polecenie `release` robi: tag → build all → checksums → `gh release create` z assets.

## Użycie

```bash
gh auth login                            # jednorazowo

taskfile run test                        # go test
taskfile run build-linux --var VERSION=1.0.0   # Linux amd64 + arm64
taskfile run build-all --var VERSION=1.0.0     # 4 platformy parallel + checksums
taskfile run release --var VERSION=1.0.0       # tag + build + gh release create
taskfile run verify --var VERSION=1.0.0        # gh release view
```

## Wymagane

| Narzędzie | Instalacja |
|-----------|------------|
| `gh` CLI | https://cli.github.com/ |
| `GITHUB_TOKEN` | https://github.com/settings/tokens (scope: `repo`) |
