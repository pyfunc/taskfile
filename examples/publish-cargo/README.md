# Publish Cargo — Rust Crate

Publikacja crate'a Rust na crates.io za pomocą Taskfile.

## Struktura projektu

```
publish-cargo/
├── Taskfile.yml      # Pipeline: fmt → clippy → test → publish
├── Cargo.toml        # Metadata crate'a
├── src/
│   └── lib.rs
├── tests/
│   └── integration.rs
└── README.md
```

## Pipeline

```
fmt ────┐
clippy ─┤── (parallel) ── build ── publish-dry ── publish
test ───┘
```

## Użycie

```bash
# Konfiguracja tokenu crates.io
taskfile auth setup --registry crates

# Formatowanie + lint
taskfile run fmt
taskfile run clippy

# Testy
taskfile run test

# Build release
taskfile run build

# Dry-run publish (sprawdzenie metadanych)
taskfile run publish-dry

# Publikacja na crates.io
taskfile run publish --var VERSION=1.0.0

# Build dla wielu platform
taskfile run build-all-targets

# Pełny release
taskfile run release --var VERSION=1.0.0

# Weryfikacja
taskfile run verify
```

## Wymagane tokeny

| Zmienna | Gdzie uzyskać |
|---------|---------------|
| `CARGO_TOKEN` | https://crates.io/settings/tokens |

Token zapisz w `.env`:
```
CARGO_TOKEN=cio_abc123...
```

Lub użyj `taskfile auth setup --registry crates`.
