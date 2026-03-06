# TODO

## 🎯 Current Tasks

### High Priority
- [x] Update all examples with README files
- [x] Add Examples section to main README
- [x] Update examples/README.md with comprehensive guide
- [x] Update CHANGELOG with latest changes
- [x] Update TODO with current priorities
- [x] Update documentation for new syntax features
- [x] Diagnostics refactoring: error categorization (config/env/infra/runtime)
- [x] Pre-run validation in runner (catches errors before task execution)
- [x] Exit code classification (127→config, 137→infra, etc.)
- [x] Doctor command: `--report` (JSON for CI) and `--examples` flags
- [x] Fix all example .env files (24 warnings → 0)
- [x] Add 38 new diagnostics tests (total: 432)

### Medium Priority
- [x] Create comprehensive docs/ guides
- [x] Document CI/CD generation features
- [x] Add more validation examples
- [ ] Add embedded functions examples to documentation
- [ ] Create migration guide from other tools
- [ ] Add `taskfile check-examples` standalone command for CI
- [ ] Add `.env.example` auto-generation from Taskfile env definitions

### Low Priority
- [ ] Add more example projects
- [ ] Create video tutorials
- [ ] Add diagnostics to web UI dashboard

## ✅ Recently Completed

- [x] Diagnostics refactoring (Phase 5):
  - IssueCategory enum, DiagnosticIssue class, CATEGORY_LABELS/HINTS
  - Converted all `self.issues.append()` → `self._add_issue()` with categories
  - Categorized report output grouped by config/env/infra/runtime
  - JSON report via `get_report_dict()` / `print_report_json()`
  - `_fix_missing_env_files()` auto-fix (copies from .example)
  - `validate_before_run()` pre-flight check for runner
  - `_classify_exit_code()` in runner/commands.py
  - `check_examples()` static method for CI validation
  - `generate_env_example()` for .env template generation
- [x] Fixed all 24 example validation warnings:
  - Created missing .env files from .example templates
  - Added new .env.example templates for edge-iot, cloud-aws, iac-terraform
- [x] Added 38 new tests in test_diagnostics.py
- [x] Updated README.md with Diagnostics & Validation section
- [x] Updated CHANGELOG.md with Phase 5 refactoring
- [x] Updated comparisons/README.md with diagnostic features in feature matrix
- [x] Updated TEST_REPORT.md (26/26 examples passing)
- [x] Updated TODO.md
- [x] Added VPS auto-configuration (VPS_IP) to examples
- [x] Added CI/CD generation tasks (ci-generate)
- [x] Added deployment validation (validate-deploy, validate-vm)
- [x] Added preflight checks
- [x] Created README for minimal, saas-app, multiplatform, codereview.pl examples
- [x] Updated main README.md with new syntax features documentation
- [x] Updated docs/FORMAT.md, docs/USAGE.md with new sections

## 🐛 Known Issues

<!-- Issues will be automatically added here when using goal -t -->

## 📝 Notes

- Examples now have comprehensive README files with .env.example templates for all environments
- VPS deployment simplified (just add VPS_IP to .env)
- CI/CD generation works for GitHub Actions and GitLab CI
- Validation supports Docker and Vagrant VM
- Error classification helps users distinguish taskfile config errors from software failures
- `taskfile doctor --report` provides CI-friendly JSON output
- Pre-run validation prevents cryptic subprocess failures by checking config first
- All 26 examples pass validation with 0 warnings
- 432 tests passing

Last updated: 2026-03-06