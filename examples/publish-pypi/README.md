# Publish PyPI — Python Package

Publikacja paczki Python na PyPI za pomocą Taskfile.

## Taskfile.yml — 63 linie

```
lint ──┐
       ├── (parallel) ── build (+ twine check) ── publish
test ──┘
```

**Brak sekcji `environments`** — nie jest potrzebna dla prostego pipeline publikacji.

## Użycie

```bash
taskfile auth setup --registry pypi  # jednorazowo

taskfile run test                    # pytest + coverage
taskfile run build                   # wheel + sdist + twine check
taskfile run publish                 # upload do PyPI
taskfile run release --var VERSION=1.0.0  # tag + build + publish
taskfile run verify --var VERSION=1.0.0   # sprawdź czy się instaluje
```

## Wymagane tokeny

| Zmienna | Gdzie uzyskać |
|---------|---------------|
| `PYPI_TOKEN` | https://pypi.org/manage/account/token/ |

```bash
taskfile auth setup --registry pypi
```
