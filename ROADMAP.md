# Roadmap

The high-level direction for `taskfile`. For day-to-day follow-ups see
[`TODO.md`](TODO.md). For shipped items see
[`CHANGELOG.md`](CHANGELOG.md).

## Principles

- **One YAML file** describes environments, tasks, groups, and deploy targets.
- **Zero new DSL** — leans on existing YAML + familiar shell.
- **Local first** — everything works offline before it reaches CI.
- **Incremental adoption** — you can import Makefiles, GitHub Actions,
  GitLab CI, and shell scripts instead of rewriting them.
- **Group operations** — a single command should scale from one project
  to a folder full of them.

---

## Shipped (highlights)

### 0.3.x
- Environments, tasks, environment groups, fleet management.
- Multi-platform deploy (Docker Compose, Podman Quadlet, Kubernetes).
- CI/CD generation (GitHub Actions, GitLab CI, Jenkins, CircleCI, Drone).
- Registry authentication and multi-registry publishing.
- Scaffold templates (`taskfile scaffold <name>`).
- Diagnostics (`taskfile doctor`, `taskfile validate`, `taskfile watch`,
  `taskfile graph`).
- REST API server (`taskfile serve`).
- Package management (`taskfile pkg install / search`).
- Interactive mode, tab completion, colorised output.

### Current (Unreleased)
- **`taskfile workspace`** — multi-project group operations
  (`list`, `status`, `tasks`, `workflows`, `validate`, `analyze`, `compare`,
  `fix`, `run`, `doctor`, `deploy`).
- **`doql workspace`** — companion command focused on `.doql.css`.
- Peer-benchmarking across multiple roots with CSV export.
- Manifest fixing (empty workflows, orphans, missing workflows).

---

## Near-term (next minor)

### Workspace
- `workspace run --parallel N` — parallel execution across projects.
- `workspace graph` — dependency graph across projects (mermaid/DOT).
- `workspace compare --format {json,markdown}` — richer output formats.
- `workspace search QUERY` — grep across task commands and workflow bodies.
- Per-project "score" column (0–100) summarising health + peer conformance.

### Core
- First-class JSON output for `doctor` (needed by `workspace doctor`).
- Structured logs (`--log-format json`) for all commands.
- Better error messages when Taskfile references undefined environments.

### Docs
- Dedicated "Recipes" section in `docs/WORKSPACE.md` (common multi-root
  flows, rollback, staged rollout across many services).
- Asciinema demos: workspace compare, fleet rolling deploy.

---

## Medium-term

### Workspace
- `workspace sync-manifests` — interactive: propagate common tasks from
  peers back into outliers.
- `workspace install` — parallel bootstrap (`pip install -e .`,
  `npm install`, `cargo fetch`) for a folder of freshly cloned projects.
- Plugin system for custom analyzers (e.g. security scan, license check)
  that appear as extra columns in `workspace compare` output.

### Core
- OpenAPI 3.1 generator for `taskfile serve` (separate from the existing
  informal REST API).
- Native Windows support (currently Linux/macOS-first; some shell-isms).
- Task-level caching with explicit cache keys (like Turbo/Nx).

### Ecosystem
- VS Code extension: inline `taskfile` runner + environment switcher +
  workspace explorer view.
- pre-commit hooks that run `workspace validate` automatically.

---

## Long-term / exploratory

- **Distributed execution** — run the same task across a fleet of dev
  machines or CI runners with a single command.
- **Task marketplace** — `taskfile pkg install` already works; a curated
  registry of reusable task bundles (lint, test, deploy-to-k8s, …) would
  accelerate adoption.
- **Self-hosted web UI** — on top of `taskfile serve` with environment
  groups, fleet status, and workspace reports.
- **Speculative execution** — for `workspace compare` style analyses,
  compute against a snapshot instead of re-scanning every project.

---

## Non-goals

- Replacing Make/CMake/Bazel for heavy build orchestration —
  `taskfile` is a glue layer, not a build system.
- Implementing a new DSL; YAML + shell + embedded functions is enough.
- Becoming a CI system — we generate CI configs, we don't host runners.
- Package-manager semantics — `taskfile pkg` installs task bundles, not
  application dependencies.
