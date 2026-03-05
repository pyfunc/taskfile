# Publish npm — Node.js Package

Publikacja paczki Node.js na npm za pomocą Taskfile.

## Struktura projektu

```
publish-npm/
├── Taskfile.yml      # Pipeline: lint → test → build → publish
├── package.json      # Metadata paczki
├── tsconfig.json     # TypeScript config
├── src/
│   └── index.ts
├── tests/
│   └── index.test.ts
└── README.md
```

## Pipeline

```
lint ──┐
       ├── (parallel) ── build ── pack ── publish
test ──┘
```

## Użycie

```bash
# Konfiguracja tokenu npm
taskfile auth setup --registry npm

# Testy + lint
taskfile run test
taskfile run lint

# Build TypeScript
taskfile run build

# Dry-run pack (sprawdzenie co wejdzie do paczki)
taskfile run pack

# Publikacja na npm
taskfile run publish --var VERSION=1.0.0

# Publikacja wersji beta
taskfile run publish-beta --var VERSION=1.0.0-beta.1

# Pełny release
taskfile run release --var VERSION=1.0.0

# Weryfikacja
taskfile run verify --var VERSION=1.0.0
```

## Wymagane tokeny

| Zmienna | Gdzie uzyskać |
|---------|---------------|
| `NPM_TOKEN` | `npm token create` lub https://www.npmjs.com/settings/tokens |

Token zapisz w `.env`:
```
NPM_TOKEN=npm_abc123...
```

Lub użyj `taskfile auth setup --registry npm`.
