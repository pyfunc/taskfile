# Workspace — Multi-Project Group Operations

`taskfile workspace` provides group operations across many local projects at once.
Discover projects under a given path, filter them by manifest contents
(`Taskfile.yml` tasks or `app.doql.css` workflows), and run actions like
`run`, `doctor`, `validate`, `deploy`, `fix`, and `analyze` across all matches.

## Why workspace?

You keep dozens of small projects inside folders like `~/github/semcod/`,
`~/github/oqlos/`. Each has its own `Taskfile.yml` and/or `app.doql.css`.
Typical needs:

- Which projects have a `test` task? Which have a `deploy` task?
- Run `lint` in every project that supports it.
- Quickly spot projects with manifest errors (empty workflows, missing sections).
- Deploy all Docker-enabled projects at once.
- Fix recurring issues across dozens of projects with a single command.

The workspace module solves these by discovering projects, filtering them, and
running group operations with a `--depth` limit and rich filters.

## Project discovery

A folder is considered a project if it contains any of:
`pyproject.toml`, `package.json`, `Dockerfile`, `setup.py`, `Makefile`, `Taskfile.yml`.

Folders `venv`, `.venv`, `node_modules`, `__pycache__`, `dist`, `build`,
`.code2llm_cache`, hidden folders (`.git`, `.idea`, ...) and logs directories
are always skipped.

`--depth N` limits how deep the walker goes. Default is `2` (direct children
and one level of nesting). If a folder is already a project, the walker does
not descend into it further.

## Commands

```text
taskfile workspace --help
```

| Command                    | Description |
|----------------------------|-------------|
| `list`                     | List matching projects (with filters) |
| `status`                   | One-row-per-project overview (git, TF, doql, Docker, counts) |
| `tasks`                    | Frequency table: tasks across projects |
| `workflows`                | Frequency table: doql workflows across projects |
| `validate`                 | Report manifest issues per project |
| `analyze` / `analyze -o X` | Full metrics + issues + recs, table or CSV |
| `compare` / `compare -o X` | Peer-benchmarked comparison across one or more roots |
| `fix`                      | Apply manifest fixes (empty workflows, orphans, missing) |
| `run <task>`               | Run a task in every project that has it |
| `doctor`                   | Run `taskfile doctor` in every project |
| `deploy`                   | `taskfile up` or `docker compose up -d` across Docker projects |

### Global options

All commands accept:

- `--root PATH` / `-r PATH` — scan base (default: `.`)
- `--depth N` / `-d N` — max recursion depth (default: `2`)
- `--name REGEX` — filter project by name (regex, case-insensitive) — on most commands

`list` also accepts: `--has-task`, `--has-workflow`, `--taskfile-only`, `--doql-only`,
`--docker-only`, `--tasks` (show tasks column), `--workflows` (show workflows column).

## Demos

### Discover projects under a workspace

```bash
taskfile workspace list --root ~/github/semcod --depth 2
taskfile workspace list --root ~/github/oqlos --depth 2
```

### What tasks do these projects share?

```bash
taskfile workspace tasks --root ~/github/semcod
```

Output shows tasks ordered by frequency (how many projects have each task).
Useful for spotting de-facto conventions and candidate tasks to standardize on.

### Filter: find projects with a specific task

```bash
# All projects that define a `publish` task
taskfile workspace list --root ~/github/semcod --has-task publish

# All projects with both Docker and a `deploy` task
taskfile workspace list --root ~/github/semcod --docker-only --has-task deploy
```

### Run a task across many projects

```bash
# Dry-run: show what would execute
taskfile workspace run lint --root ~/github/semcod --dry-run

# Actually run lint in every project that has it
taskfile workspace run lint --root ~/github/semcod

# Stop on the first failure
taskfile workspace run test --root ~/github/semcod --fail-fast

# Only projects whose name starts with 'a'
taskfile workspace run build --root ~/github/semcod --name '^a'
```

### Group doctor

```bash
taskfile workspace doctor --root ~/github/semcod
taskfile workspace doctor --root ~/github/oqlos -v   # verbose
```

### Validate manifests

```bash
taskfile workspace validate --root ~/github/semcod
taskfile workspace validate --root ~/github/oqlos --strict   # non-zero exit on any issue
```

### Full analysis (CSV export)

```bash
# Print table
taskfile workspace analyze --root ~/github/semcod

# Export to CSV for spreadsheet/BI tools
taskfile workspace analyze --root ~/github/semcod -o semcod_analysis.csv
```

CSV columns: `path`, `name`, `taskfile_tasks`, `taskfile_has_pipeline`,
`taskfile_has_docker`, `taskfile_has_environments`, `doql_workflows`,
`doql_has_deploy`, `has_git`, `issues`, `recommendations`.

### Peer-benchmarked comparison (multi-root)

When you keep projects in multiple folders, compare them all in one CSV with
peer-benchmarking (which common tasks/workflows are *you* missing?):

```bash
# Compact summary to stdout
taskfile workspace compare -r ~/github/semcod -r ~/github/oqlos

# Full CSV report (recommended)
taskfile workspace compare -r ~/github/semcod -r ~/github/oqlos \
  -o ~/github/projects_report.csv

# Stricter "common" definition — task must be present in 70%+ of peers
taskfile workspace compare -r ~/github/semcod --threshold 0.7 -o report.csv
```

CSV columns:

| Column | Meaning |
|--------|---------|
| `path`, `name` | Absolute path and folder name |
| `taskfile_tasks`, `doql_workflows` | Count of tasks / workflows |
| `taskfile_has_pipeline`, `taskfile_has_docker`, `taskfile_has_environments` | Taskfile structural flags |
| `doql_entities`, `doql_databases`, `doql_interfaces` | DOQL structural counts |
| `doql_has_app`, `doql_has_deploy` | DOQL structural flags |
| `median_tasks`, `median_workflows` | Peer median across all projects |
| `tasks_vs_median`, `workflows_vs_median` | How this project compares to median (+/-) |
| `empty_workflows` | Workflows declared but with no `step-1` |
| `orphan_workflows` | doql workflows with no matching Taskfile task |
| `tasks_missing_in_doql` | Tasks in Taskfile but no workflow |
| `missing_common_tasks` | Tasks present in most peers but missing here |
| `missing_common_workflows` | Workflows present in most peers but missing here |
| `issues` | Human-readable list of problems |
| `recommendations` | Prioritized list of improvements |

This CSV is the intended single source of truth for "what should I fix across
all my projects". Load it into a spreadsheet, sort by issues count, and work
through it top-down.

### Batch-fix manifest errors

```bash
# See what would change
taskfile workspace fix --root ~/github/semcod --dry-run

# Apply fixes
taskfile workspace fix --root ~/github/semcod
```

Fixes performed:

- Remove `import-makefile-hint` task if the project has no `Makefile`.
- Fill empty doql workflows (no `step-1`) with commands from the matching `Taskfile.yml` task.
- Remove doql workflows that have no matching task (orphans) when they are empty.
- Add doql workflows for Taskfile tasks that don't have one yet.

### Group deploy

```bash
# Preview what would deploy
taskfile workspace deploy --root ~/github/semcod --dry-run

# Actually deploy
taskfile workspace deploy --root ~/github/semcod

# Deploy only specific projects
taskfile workspace deploy --root ~/github/semcod --name 'algi|prellm'
```

For every Docker-enabled project, `deploy` runs `taskfile up` when that task
exists, else `docker compose up -d`.

## Python API

The CLI is a thin layer over `taskfile.workspace`. You can use the API directly
in scripts and higher-level tools:

```python
from pathlib import Path
from taskfile.workspace import (
    discover_projects,
    filter_projects,
    validate_project,
    fix_project,
    analyze_project,
    run_in_project,
)

projects = discover_projects(Path("~/github/semcod").expanduser(), max_depth=2)
deployable = filter_projects(projects, has_task="up", has_docker=True)

for p in deployable:
    result = run_in_project(p, ["taskfile", "up"], timeout=300)
    print(p.name, "OK" if result.success else "FAIL")
```

Top-level API exports:

- `Project` — dataclass describing a discovered project
- `CommandResult` — outcome of running a command in a project
- `FixResult` — outcome of `fix_project`
- `discover_projects(root, max_depth)` — walk and collect projects
- `filter_projects(projects, **filters)` — filter by task/workflow/etc.
- `validate_project(project)` — list of issues (strings)
- `analyze_project(project)` — dict of metrics + issues + recommendations
- `compare_projects(projects, common_threshold=0.5)` — list of dicts with peer-benchmark metrics
- `fix_project(project)` — apply fixes, return `FixResult`
- `run_in_project(project, command, timeout, capture)` — run a shell command
- `run_task_in_projects(projects, task_name, timeout)` — convenience wrapper

## Companion command: `doql workspace`

The [doql](https://github.com/softreck/doql) CLI exposes a parallel
`workspace` command focused on `app.doql.css` manifests. It shares discovery
rules and (optionally) delegates `fix` back to `taskfile.workspace`:

```bash
doql workspace list     --root ~/github/oqlos
doql workspace analyze  --root ~/github/oqlos -o oqlos_report.csv
doql workspace validate --root ~/github/oqlos
doql workspace run build --root ~/github/oqlos
doql workspace fix      --root ~/github/oqlos   # requires `pip install taskfile`
```

`doql workspace` analysis columns surface DOQL-specific data:
workflows, entities, databases, and interfaces (e.g. `cli`, `web`, `api`).
`taskfile workspace analyze` focuses on Taskfile-centric data
(task count, pipeline presence, Docker markers).

Use whichever matches the manifest you want to reason about; both can be
combined via shell scripts and CSV intermediates.

## Design notes

- **Read-only by default.** `list`, `status`, `tasks`, `workflows`,
  `validate`, `analyze`, `run --dry-run`, `fix --dry-run`, `deploy --dry-run`
  never mutate anything on disk.
- **Mutation commands** (`fix`, `run`, `deploy`) are explicit — you always
  know when a command writes files or spawns subprocesses.
- **Fixed exclusion list** is intentionally conservative. Add your own
  markers to `taskfile.workspace.PROJECT_MARKERS` or forks of the walker
  if you want different semantics.
- **No cross-project state.** Each project is scanned/fixed/run independently.
