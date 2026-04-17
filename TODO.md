# TODO

Active follow-ups for the `taskfile` package.

---

## Workspace (multi-project operations)

### Stability
- [ ] `workspace run` — add `--parallel N` to run tasks in parallel across
      multiple projects (current impl is serial).
- [ ] `workspace run` — honor per-project timeout overrides from
      Taskfile (`env.timeout` or task metadata).
- [ ] `workspace doctor` — parse structured output from `taskfile doctor`
      (JSON mode) instead of string-matching keywords.

### Features
- [ ] `workspace graph` — render a DOT/mermaid graph of task dependencies
      across many projects; highlight shared/unique tasks.
- [ ] `workspace install` — run `pip install -e .` / `npm install` in every
      project in parallel (bootstrap a fresh clone).
- [ ] `workspace sync-manifests` — inverse of `fix`: propagate tasks that
      exist in most peers back into outliers (interactive).
- [ ] `workspace search QUERY` — grep task commands, descriptions, and
      workflow bodies across all projects.

### CSV / reporting
- [ ] `workspace compare` — add `--format json` and `--format markdown` in
      addition to CSV.
- [ ] `workspace compare` — emit a per-project recommendations file
      (`<project>/WORKSPACE_RECS.md`) when `--write-recs` is passed.
- [ ] `workspace analyze` / `compare` — add a "score" column (0–100) based
      on completeness + peer conformance.

### Documentation / examples
- [ ] Add `examples/workspace/` with multiple tiny projects + a Makefile
      target that runs the full workspace flow.  ← DONE
- [ ] Add `docs/WORKSPACE.md` section "Recipes": common multi-root flows.
- [ ] Record an asciinema demo of `workspace compare` producing a CSV.

## doql companion command
- [ ] Add `doql workspace doctor` that runs `doql validate` in each project
      and aggregates errors.
- [ ] Add `doql workspace build --parallel` for monorepo-scale builds.

## Tests
- [ ] Add end-to-end test that spins up 3 fake projects in `tmp_path`,
      runs `workspace compare`, and asserts CSV header + row count.
- [ ] Smoke-test `workspace compare` against `~/github/semcod` in CI when
      the folder is present (skip otherwise).
