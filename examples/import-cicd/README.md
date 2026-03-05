# Example: CI/CD Import

Demonstrates the `taskfile import` command — converting existing CI/CD configs, Makefiles, and shell scripts INTO Taskfile.yml format.

## Features Shown

- **`taskfile import`** — auto-detect and convert external formats
- **GitHub Actions** → Taskfile.yml (jobs → tasks, steps → commands, needs → deps)
- **GitLab CI** → Taskfile.yml (jobs → tasks, stages → pipeline, needs → deps)
- **Makefile** → Taskfile.yml (targets → tasks, prerequisites → deps, variables)
- **Shell script** → Taskfile.yml (functions → tasks, main body → task)
- **Dockerfile** → Taskfile.yml (build stages → tasks)

## Source Files

```
sources/
├── ci.yml              # GitHub Actions workflow
├── .gitlab-ci.yml      # GitLab CI config
├── Makefile            # GNU Make
└── deploy.sh           # Shell script with functions
```

## Usage

```bash
# Import a single source
taskfile import sources/ci.yml --type github-actions -o imported-github.yml
taskfile import sources/.gitlab-ci.yml --type gitlab-ci -o imported-gitlab.yml
taskfile import sources/Makefile -o imported-makefile.yml
taskfile import sources/deploy.sh --type shell -o imported-shell.yml

# Auto-detect type (works for Makefile, .gitlab-ci.yml, *.sh)
taskfile import sources/Makefile -o imported-makefile.yml

# Import all at once via this example's Taskfile
taskfile run import-all
```

## What Gets Converted

### GitHub Actions → Taskfile

| GitHub Actions | Taskfile |
|---------------|----------|
| `jobs:` | `tasks:` |
| `steps[].run:` | `cmds:` |
| `needs:` | `deps:` |
| `env:` | `variables:` |
| `steps[].uses:` | `echo '[skip] GitHub Action: ...'` |
| Job names | Task names (slugified) |

### GitLab CI → Taskfile

| GitLab CI | Taskfile |
|-----------|----------|
| Job definitions | `tasks:` |
| `script:` | `cmds:` |
| `stage:` | `stage:` field on task |
| `stages:` order | `pipeline.stages` |
| `needs:` | `deps:` |
| `variables:` | `variables:` |

### Makefile → Taskfile

| Makefile | Taskfile |
|----------|----------|
| Targets | `tasks:` |
| Prerequisites | `deps:` |
| Recipe lines | `cmds:` |
| `VAR = value` | `variables:` |

### Shell Script → Taskfile

| Shell Script | Taskfile |
|-------------|----------|
| Functions | `tasks:` (one per function) |
| Function body | `cmds:` |
| No functions? | Single `main` task |

## After Import

The generated Taskfile is a starting point. You should:

1. Review and adjust task descriptions
2. Replace `echo '[skip] GitHub Action: ...'` with equivalent commands
3. Add `environments` if needed
4. Add `@remote` prefix for SSH commands
5. Run `taskfile validate` to check
