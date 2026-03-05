## [Unreleased]

### Features

- **Embedded functions** — `functions` section in Taskfile.yml with Python/shell/Node/binary support
- **`@fn` prefix** — call embedded functions from task commands: `@fn notify arg1`
- **`@python` prefix** — run inline Python from task commands: `@python print('hello')`
- **`retries` + `retry_delay`** — auto-retry failed commands (Ansible-inspired)
- **`timeout`** — command timeout in seconds, returns exit code 124 on timeout
- **`tags`** — selective task execution with `--tags` CLI flag
- **`register`** — capture command stdout into a variable for chaining
- **`taskfile import`** — convert GitHub Actions, GitLab CI, Makefile, shell scripts, Dockerfile INTO Taskfile.yml

### Docs

- Add `comparisons/taskfile-vs-ansible.md` — full Ansible comparison with migration guide
- Update `comparisons/README.md` — add new features to feature matrix
- Update `examples/README.md` — add functions-embed and import-cicd examples
- Update main `README.md` — new features, 24 examples, import command, functions reference

### Examples

- Add `examples/functions-embed/` — demonstrates functions, @fn, @python, retries, tags, register
- Add `examples/import-cicd/` — demonstrates `taskfile import` from 4 CI/CD formats
- Update `examples/saas-app/` — add retries, tags, timeout to deploy task
- Update `examples/fleet-rpi/` — add tags, retries, timeout to deploy/provision tasks
- Fix `examples/publish-cargo/` — quote YAML desc with colons
- Fix `examples/publish-npm/` — quote YAML desc with colons

### Core

- Add `Function` dataclass to `models.py`
- Add `functions` field to `TaskfileConfig`
- Add `retries`, `retry_delay`, `timeout`, `tags`, `register` fields to `Task`
- Add `_run_function`, `_run_inline_python`, `_exec_function_*` methods to runner
- Add retry logic to `_execute_commands`
- Add timeout support to `run_command` via `subprocess.TimeoutExpired`
- Add register/capture support to `run_command`
- Add `--tags` option to `run` CLI command
- Add `taskfile import` CLI command
- Add `src/taskfile/importer.py` — import module (5 formats)

### Tests

- Expand E2E tests: 283 → 320 tests
- Add `TestFunctionsEmbedExample` — 12 tests for functions example
- Add `TestImportCICDExample` — 3 tests for import example
- Add `TestImporterModule` — 7 tests for importer module
- Add `TestAnsibleInspiredFeatures` — 10 tests for retries/timeout/tags/register/functions
- Add `TestCLIImportCommand` — 3 tests for import CLI
- Add `TestCLITagsFlag` — 3 tests for --tags flag

## [0.3.19] - 2026-03-05

### Docs
- Update project/README.md
- Update project/context.md

### Other
- Update project/analysis.toon
- Update project/calls.mmd
- Update project/calls.png
- Update project/compact_flow.mmd
- Update project/compact_flow.png
- Update project/dashboard.html
- Update project/evolution.toon
- Update project/flow.mmd
- Update project/flow.png
- Update project/flow.toon
- ... and 3 more files

## [0.3.18] - 2026-03-05

### Docs
- Update CHANGELOG.md
- Update README.md
- Update comparisons/README.md
- Update comparisons/taskfile-vs-ansible.md
- Update examples/README.md
- Update examples/functions-embed/README.md
- Update examples/import-cicd/README.md
- Update examples/publish-desktop/README.md
- Update examples/publish-mobile/README.md

### Test
- Update tests/test_e2e_examples.py

### Other
- Update examples/fleet-rpi/Taskfile.yml
- Update examples/functions-embed/Taskfile.yml
- Update examples/functions-embed/scripts/health.sh
- Update examples/functions-embed/scripts/report.py
- Update examples/import-cicd/Taskfile.yml
- Update examples/import-cicd/sources/.gitlab-ci.yml
- Update examples/import-cicd/sources/Makefile
- Update examples/import-cicd/sources/ci.yml
- Update examples/import-cicd/sources/deploy.sh
- Update examples/publish-cargo/Taskfile.yml
- ... and 7 more files

## [0.3.17] - 2026-03-05

## [0.3.16] - 2026-03-05

### Docs
- Update comparisons/taskfile-vs-ansible.md
- Update examples/include-split/README.md

## [0.3.15] - 2026-03-05

### Docs
- Update examples/ci-generation/README.md
- Update examples/script-extraction/README.md

### Other
- Update examples/ci-generation/Taskfile.yml
- Update examples/include-split/Taskfile.yml
- Update examples/include-split/tasks/build.yml
- Update examples/include-split/tasks/deploy.yml
- Update examples/include-split/tasks/test.yml
- Update examples/script-extraction/Taskfile.yml
- Update examples/script-extraction/scripts/build.sh
- Update examples/script-extraction/scripts/ci-pipeline.sh
- Update examples/script-extraction/scripts/deploy.sh
- Update examples/script-extraction/scripts/health-check.sh
- ... and 8 more files

## [0.3.14] - 2026-03-05

### Docs
- Update README.md
- Update comparisons/README.md
- Update comparisons/taskfile-vs-ansible.md
- Update comparisons/taskfile-vs-dagger.md
- Update comparisons/taskfile-vs-go-task.md
- Update comparisons/taskfile-vs-just.md
- Update comparisons/taskfile-vs-mage.md
- Update comparisons/taskfile-vs-make.md
- Update examples/README.md
- Update examples/ci-pipeline/README.md
- ... and 14 more files

### Test
- Update tests/test_e2e_examples.py

### Other
- Update examples/ci-pipeline/Taskfile.yml
- Update examples/cloud-aws/Taskfile.yml
- Update examples/edge-iot/Taskfile.yml
- Update examples/fleet-rpi/Taskfile.yml
- Update examples/fullstack-deploy/Taskfile.yml
- Update examples/iac-terraform/Taskfile.yml
- Update examples/kubernetes-deploy/Taskfile.yml
- Update examples/monorepo-microservices/Taskfile.yml
- Update examples/multi-artifact/Taskfile.yml
- Update examples/multiplatform/Taskfile.yml
- ... and 21 more files

## [0.3.13] - 2026-03-05

## [0.3.12] - 2026-03-05

### Other
- Update examples/codereview.pl/.github/workflows/taskfile.yml
- Update examples/run-all.sh

## [0.3.11] - 2026-03-05

### Test
- Update tests/test_auth.py
- Update tests/test_fleet.py

## [0.3.10] - 2026-03-05

### Docs
- Update CHANGELOG.md
- Update README.md
- Update TODO.md
- Update examples/README.md
- Update examples/codereview.pl/README.md
- Update examples/minimal/README.md
- Update examples/multiplatform/README.md
- Update examples/saas-app/README.md
- Update project/README.md
- Update project/context.md

### Test
- Update tests/test_health.py
- Update tests/test_landing.py
- Update tests/test_models.py
- Update tests/test_provisioner.py
- Update tests/test_quadlet.py
- Update tests/test_release.py
- Update tests/test_runner.py
- Update tests/test_scaffold.py
- Update tests/test_setup.py

### Other
- Update examples/codereview.pl/Taskfile.yml
- Update examples/multiplatform/Taskfile.yml
- Update project.sh
- Update project/analysis.toon
- Update project/calls.mmd
- Update project/calls.png
- Update project/compact_flow.mmd
- Update project/compact_flow.png
- Update project/dashboard.html
- Update project/evolution.toon
- ... and 6 more files

## [0.4.0] - 2026-03-05

### Summary

feat(examples): comprehensive documentation update with CI/CD generation and deployment validation

### Features

- examples: add README.md to minimal/ with quick start guide
- examples: add README.md to saas-app/ with staging/prod workflow
- examples: add README.md to multiplatform/ with validation examples
- examples: add README.md to codereview.pl/ with CI/CD generation docs
- examples: add ci-generate task for GitHub Actions and GitLab CI
- examples: add validate-deploy task for Docker validation
- examples: add validate-vm task for Vagrant VM validation
- examples: add preflight checks for prerequisites
- examples: add init task for auto-generating .env files
- examples: add env-check task for configuration validation
- examples: add deploy-all task for SaaS + Desktop deployment
- examples: add VPS auto-configuration via VPS_IP variable

### Docs

- docs: update examples/README.md with comprehensive guide
- docs: update main README.md with Examples section
- docs: add task table to examples README
- docs: document CI/CD generation workflow
- docs: document deployment validation options

### Other

- build: update all examples Taskfile.yml files
- examples: add ssh-key-setup task
- examples: add vps-setup and vps-setup-check tasks

## [0.3.9] - 2026-03-05

### Summary

feat(examples): multi-language support with 2 supporting modules

### Other

- build: update Makefile
- build: update Makefile
- build: update Makefile
- build: update Makefile
- scripts: update run-all.sh
- scripts: update run-codereview.sh
- scripts: update run-minimal.sh
- scripts: update run-multiplatform.sh
- scripts: update run-saas-app.sh
- build: update Makefile


## [0.3.8] - 2026-03-05

### Summary

refactor(docs): code analysis engine

### Docs

- docs: update README
- docs: update context.md

### Other

- update project/analysis.toon
- update project/calls.mmd
- update project/calls.png
- update project/compact_flow.mmd
- update project/compact_flow.png
- update project/dashboard.html
- update project/evolution.toon
- update project/flow.mmd
- update project/flow.png
- update project/flow.toon
- ... and 3 more


## [0.3.7] - 2026-03-05

### Summary

refactor(build): configuration management system

### Core

- update src/taskfile/cigen/drone.py
- update src/taskfile/cigen/gitlab.py
- update src/taskfile/cirunner.py
- update src/taskfile/cli/deploy.py
- update src/taskfile/compose.py
- update src/taskfile/parser.py
- update src/taskfile/runner.py


## [0.3.6] - 2026-03-05

### Summary

feat(docs): code analysis engine

### Core

- update src/taskfile/cli/main.py
- update src/taskfile/models.py
- update src/taskfile/parser.py
- update src/taskfile/runner.py
- update src/taskfile/scaffold/__init__.py
- update src/taskfile/scaffold/multiplatform.py

### Docs

- docs: update README
- docs: update context.md

### Other

- update .idea/taskfile.iml
- config: update Taskfile.yml
- update project/analysis.toon
- update project/evolution.toon
- update project/project.toon


## [0.3.5] - 2026-03-05

### Summary

refactor(build): code analysis engine

### Core

- update src/taskfile/cigen.py
- update src/taskfile/cigen/__init__.py
- update src/taskfile/cigen/base.py
- update src/taskfile/cigen/drone.py
- update src/taskfile/cigen/gitea.py
- update src/taskfile/cigen/github.py
- update src/taskfile/cigen/gitlab.py
- update src/taskfile/cigen/jenkins.py
- update src/taskfile/cigen/makefile.py
- update src/taskfile/cli.py
- ... and 13 more

### Docs

- docs: update README
- docs: update context.md

### Test

- update tests/test_cigen.py
- update tests/test_cli.py
- update tests/test_compose.py
- update tests/test_models.py
- update tests/test_parser.py
- update tests/test_quadlet.py
- update tests/test_runner.py
- update tests/test_scaffold.py
- update tests/test_taskfile.py

### Build

- update pyproject.toml
- update setup.py

### Config

- config: update goal.yaml

### Other

- update .idea/pyProjectModel.xml
- update .idea/taskfile.iml
- update project/analysis.toon
- update project/evolution.toon
- update project/project.toon
- update project/prompt.txt
- update taskfile/__init__.py
- update taskfile/taskfile.py


## [0.3.4] - 2026-03-03

### Summary

chore(config): new API capabilities

### Build

- update pyproject.toml


## [0.3.3] - 2026-03-03

### Summary

feat(docs): code analysis engine

### Docs

- docs: update README
- docs: update README
- docs: update context.md

### Other

- scripts: update project.sh
- update project/analysis.toon
- update project/evolution.toon
- update project/project.toon
- update project/prompt.txt


## [0.3.2] - 2026-03-03

### Summary

feat(config): config module improvements

### Build

- update pyproject.toml

### Other

- config: update Taskfile.yml


## [0.3.1] - 2026-03-03

### Summary

fix(examples): CLI interface improvements

### Core

- update src/taskfile/__init__.py
- update src/taskfile/cigen.py
- update src/taskfile/cirunner.py
- update src/taskfile/cli.py
- update src/taskfile/compose.py
- update src/taskfile/models.py
- update src/taskfile/parser.py
- update src/taskfile/quadlet.py
- update src/taskfile/runner.py
- update src/taskfile/scaffold.py

### Docs

- docs: update README
- docs: update TODO.md
- docs: update README

### Test

- update tests/__init__.py
- update tests/test_taskfile.py

### Build

- update pyproject.toml

### Config

- config: update goal.yaml

### Other

- update .gitignore
- update .idea/misc.xml
- update LICENSE
- update TICKET
- config: update .gitea-actions-deploy.yml
- config: update .github-actions-deploy.yml
- config: update .gitlab-ci.yml
- config: update Taskfile.softreck.yml
- config: update .drone.yml
- update examples/codereview.pl/.env.local
- ... and 12 more


## [1.0.1] - 2026-03-02

### Summary

feat(tests): configuration management system

### Docs

- docs: update README

### Test

- update tests/test_taskfile.py

### Build

- update setup.py

### Config

- config: update goal.yaml

### Other

- update .idea/.gitignore
- update .idea/inspectionProfiles/Project_Default.xml
- update .idea/inspectionProfiles/profiles_settings.xml
- update .idea/misc.xml
- update .idea/modules.xml
- update .idea/taskfile.iml
- update .idea/vcs.xml
- build: update Makefile
- config: update taskfile.yml
- update taskfile/__init__.py
- ... and 1 more


