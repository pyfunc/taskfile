# `workspace` — multi-project group operations

This example shows how to use `taskfile workspace` on a folder containing
several projects at once: list, analyze, validate, compare, run, and fix.

## What's in here

Three tiny sibling projects under `projects/`:

```
projects/
├── alpha/              # Complete: Taskfile + app.doql.css, all in sync
│   ├── pyproject.toml
│   ├── Taskfile.yml
│   └── app.doql.css
├── beta/               # Missing a few common tasks (lint, fmt)
│   ├── pyproject.toml
│   ├── Taskfile.yml
│   └── app.doql.css
└── gamma/              # Has tasks with no matching workflow → sync issues
    ├── pyproject.toml
    ├── Taskfile.yml
    └── app.doql.css
```

Each subfolder is a real project (detected via `pyproject.toml`).

## Run the demo

```bash
# From this folder
./run.sh
```

Which is equivalent to running these commands manually:

```bash
# 1. Discover projects
taskfile workspace list --root ./projects --depth 1

# 2. See which tasks are common and which are outliers
taskfile workspace tasks --root ./projects

# 3. Run any task across every project that has it
taskfile workspace run build --root ./projects --dry-run

# 4. Validate manifests
taskfile workspace validate --root ./projects

# 5. Peer-benchmarked comparison (CSV output)
taskfile workspace compare -r ./projects -o report.csv

# 6. Fix manifest errors in place (preview, then apply)
taskfile workspace fix --root ./projects --dry-run
taskfile workspace fix --root ./projects
```

## Expected output

`taskfile workspace compare -r ./projects` prints a table like:

```
Comparison — 3 projects (median tasks=4, workflows=4)
┌──┬────────┬───┬────┬───┬────┬──────────────────────────┬──────────────────────────┐
│ #│Project │ T │ ΔT │ W │ ΔW │ Issues                   │ Top recommendation       │
├──┼────────┼───┼────┼───┼────┼──────────────────────────┼──────────────────────────┤
│ 1│ alpha  │ 4 │  0 │ 4 │  0 │ —                        │ —                        │
│ 2│ beta   │ 2 │ -2 │ 2 │ -2 │ Few tasks (2 vs median 4)│ Add common tasks: lint…  │
│ 3│ gamma  │ 5 │ +1 │ 3 │ -1 │ 2 tasks not mirrored…    │ Add common workflows…    │
└──┴────────┴───┴────┴───┴────┴──────────────────────────┴──────────────────────────┘
```

## Python API

The same analysis via API:

```python
from pathlib import Path
from taskfile.workspace import discover_projects, compare_projects

projects = discover_projects(Path('./projects'), max_depth=1)
for r in compare_projects(projects):
    print(r['name'], r['missing_common_tasks'], r['tasks_missing_in_doql'])
```

## See also

- [`docs/WORKSPACE.md`](../../docs/WORKSPACE.md) — full reference
- [`docs/CLI.md`](../../docs/CLI.md) — CLI reference
