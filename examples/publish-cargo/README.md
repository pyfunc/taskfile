# Publish Cargo — Rust Crate

Publikacja crate'a Rust na crates.io za pomocą Taskfile.

## Taskfile.yml — 67 linii

```
fmt ────┐
clippy ─┤── (parallel) ── build ── publish (dry-run + publish)
test ───┘
```

**Brak sekcji `environments`** — nie potrzebna dla pipeline publikacji.

## Użycie

```bash
taskfile auth setup --registry crates  # jednorazowo

taskfile run fmt                       # cargo fmt --check
taskfile run clippy                    # cargo clippy
taskfile run test                      # cargo test
taskfile run build                     # cargo build --release
taskfile run build-cross               # Linux + macOS + Windows
taskfile run publish --var VERSION=1.0.0  # dry-run + publish
taskfile run release --var VERSION=1.0.0  # tag + test + publish
taskfile run verify                    # cargo search
```

## Wymagane tokeny

| Zmienna | Gdzie uzyskać |
|---------|---------------|
| `CARGO_TOKEN` | https://crates.io/settings/tokens |

```bash
taskfile auth setup --registry crates
```
