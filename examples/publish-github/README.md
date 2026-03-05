# Publish GitHub — GitHub Releases

Publikacja binarek CLI na GitHub Releases za pomocą Taskfile.

## Struktura projektu

```
publish-github/
├── Taskfile.yml      # Pipeline: build → checksum → release → upload
├── go.mod            # Go module (przykład z Go CLI)
├── main.go
└── README.md
```

## Pipeline

```
build-linux ────┐
build-linux-arm ┤
build-macos ────┤── (parallel) ── checksum ── create-release ── upload-assets ── publish
build-windows ──┘
```

## Użycie

```bash
# Konfiguracja tokenu GitHub
taskfile auth setup --registry github

# Testy
taskfile run test

# Build dla jednej platformy
taskfile run build-linux --var VERSION=1.0.0

# Build dla wszystkich platform (parallel)
taskfile run build-all --var VERSION=1.0.0

# Generowanie checksums
taskfile run checksum --var VERSION=1.0.0

# Utworzenie draftu release na GitHub
taskfile run create-release --var VERSION=1.0.0

# Upload binarek
taskfile run upload-assets --var VERSION=1.0.0

# Publikacja release (usunięcie flagi draft)
taskfile run publish --var VERSION=1.0.0

# Weryfikacja
taskfile run verify --var VERSION=1.0.0
```

## Wymagane tokeny

| Zmienna | Gdzie uzyskać |
|---------|---------------|
| `GITHUB_TOKEN` | https://github.com/settings/tokens (scope: `repo`) |

Wymagane narzędzie: [`gh` CLI](https://cli.github.com/)

```bash
gh auth login
```
