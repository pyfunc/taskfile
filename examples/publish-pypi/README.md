# Publish PyPI — Python Package

Publikacja paczki Python na PyPI za pomocą Taskfile.

## Struktura projektu

```
publish-pypi/
├── Taskfile.yml          # Pipeline: lint → test → build → publish
├── pyproject.toml        # Metadata paczki
├── src/
│   └── my_python_lib/
│       └── __init__.py
├── tests/
│   └── test_lib.py
└── README.md
```

## Pipeline

```
lint ──┐
       ├── (parallel) ── build ── check ── publish
test ──┘
```

## Użycie

```bash
# Konfiguracja tokenu PyPI
taskfile auth setup --registry pypi

# Testy + lint
taskfile run test
taskfile run lint

# Build wheel + sdist
taskfile run build

# Publikacja na TestPyPI (bezpieczne testowanie)
taskfile run publish-testpypi

# Publikacja na PyPI (produkcja)
taskfile run publish

# Pełny release: tag + build + publish
taskfile run release --var VERSION=1.0.0

# Weryfikacja — czy paczka się instaluje
taskfile run verify --var VERSION=1.0.0
```

## Wymagane tokeny

| Zmienna | Gdzie uzyskać |
|---------|---------------|
| `PYPI_TOKEN` | https://pypi.org/manage/account/token/ |

Token zapisz w `.env`:
```
PYPI_TOKEN=pypi-AgEIcH...
```

Lub użyj `taskfile auth setup --registry pypi`.
