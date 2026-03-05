# Include Split — Split Taskfile.yml into Multiple Files

Rozbicie dużego Taskfile.yml na mniejsze pliki za pomocą `include`.

## Structure

```
project/
├── Taskfile.yml              # Main file — includes + local overrides
├── tasks/
│   ├── build.yml             # Build tasks + variables
│   ├── deploy.yml            # Deploy tasks + environments (prefix: deploy)
│   └── test.yml              # Test/lint tasks
└── README.md
```

## How `include` Works

```yaml
# Taskfile.yml
include:
  - path: ./tasks/build.yml             # Merge tasks as-is
  - path: ./tasks/deploy.yml
    prefix: deploy                       # Tasks become: deploy-local, deploy-staging, deploy-prod
  - path: ./tasks/test.yml              # Simple string path also works
```

### Merge Rules

1. **Tasks** — included first, local Taskfile wins on conflict
2. **Variables** — included first, local wins
3. **Environments** — included first, local wins
4. **Prefix** — optional, prepends `{prefix}-` to included task names

### What Gets Merged

| Section | Merged | Local Wins |
|---------|--------|------------|
| `tasks` | ✅ | ✅ |
| `variables` | ✅ | ✅ |
| `environments` | ✅ | ✅ |
| `pipeline` | ❌ (main only) | — |
| `compose` | ❌ (main only) | — |

## Usage

```bash
# All included tasks are available as if defined locally
taskfile list
taskfile run build                # from tasks/build.yml
taskfile run test                 # from tasks/test.yml
taskfile run lint                 # from tasks/test.yml
taskfile run deploy-local         # from tasks/deploy.yml (prefixed)
taskfile run deploy-staging       # from tasks/deploy.yml (prefixed)
taskfile run deploy-prod          # from tasks/deploy.yml (prefixed)
taskfile run all                  # local task, depends on included tasks

# Validate (includes are resolved during parsing)
taskfile validate
```

## Include Formats

```yaml
# String shorthand
include:
  - ./tasks/build.yml

# Dict with path
include:
  - path: ./tasks/build.yml

# Dict with prefix
include:
  - path: ./tasks/deploy.yml
    prefix: deploy

# Dict with file (alias for path)
include:
  - file: ./tasks/test.yml
```

## When to Split

- **Monorepo** — each service has its own tasks file
- **Shared tasks** — common CI/test tasks reused across projects
- **Team separation** — infra team owns deploy.yml, dev team owns build.yml
- **Large Taskfile** — >100 lines → split by concern
