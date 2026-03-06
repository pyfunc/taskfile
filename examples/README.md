# Taskfile Examples

Kompletne przykłady użycia Taskfile dla różnych scenariuszy.

## Przegląd przykładów

### Podstawowe

| Przykład | Złożoność | Cechy | Kiedy użyć |
|----------|-----------|-------|------------|
| [minimal/](minimal/) | ⭐ | Podstawowe taski, bez środowisk | Start z taskfile |
| [saas-app/](saas-app/) | ⭐⭐ | local/staging/prod, pipeline | SaaS z wieloma env |
| [multiplatform/](multiplatform/) | ⭐⭐⭐ | Web + Desktop, walidacja, CI/CD gen | Aplikacje multi-platform |
| [codereview.pl/](codereview.pl/) | ⭐⭐⭐⭐ | Full CI/CD, 6 platform, Quadlet | Real-world produkcyjne |

### Publikacja (jeden rejestr)

| Przykład | Rejestr | Język | Artefakt |
|----------|---------|-------|----------|
| [publish-pypi/](publish-pypi/) | PyPI | Python | wheel + sdist |
| [publish-npm/](publish-npm/) | npm | Node.js / TypeScript | npm package |
| [publish-cargo/](publish-cargo/) | crates.io | Rust | crate |
| [publish-docker/](publish-docker/) | GHCR + Docker Hub | dowolny | Docker image (multi-arch) |
| [publish-github/](publish-github/) | GitHub Releases | Go (przykład) | binaries + checksums |

### Patterns & Import

| Przykład | Złożoność | Cechy | Kiedy użyć |
|----------|-----------|-------|------------|
| [script-extraction/](script-extraction/) | ⭐⭐ | Rozbicie Taskfile na shell/Python skrypty | Złożona logika w skryptach |
| [ci-generation/](ci-generation/) | ⭐⭐ | `pipeline` → 6 platform CI/CD gen | CI/CD z jednego źródła |
| [include-split/](include-split/) | ⭐⭐ | `include` — import z innych plików YAML | Duży Taskfile, reużywalne taski |
| [functions-embed/](functions-embed/) | ⭐⭐⭐ | `functions`, `@fn`, `@python`, retries, tags, register | Embedded multi-lang functions |
| [import-cicd/](import-cicd/) | ⭐⭐ | `taskfile import` — GitHub Actions, GitLab CI, Makefile, shell → Taskfile | Migracja z CI/CD |

### Zaawansowane

| Przykład | Złożoność | Cechy | Kiedy użyć |
|----------|-----------|-------|------------|
| [fleet-rpi/](fleet-rpi/) | ⭐⭐⭐⭐ | 6 RPi, 3 grupy, rolling/canary | Flota IoT/kiosków |
| [multi-artifact/](multi-artifact/) | ⭐⭐⭐⭐⭐ | Python+Rust+Node+Docker → 5 rejestrów | Monorepo multi-język |

### 🤖 AI Tools — integracja z narzędziami AI

| Przykład | Narzędzie | Cechy | Kiedy użyć |
|----------|-----------|-------|------------|
| [ai-aider/](ai-aider/) | [Aider](https://aider.chat) | Pełny TDD cycle, review diff/PR, lint-fix, type-fix, docstrings | CLI AI pair programmer |
| [ai-claude-code/](ai-claude-code/) | [Claude Code](https://docs.anthropic.com/en/docs/claude-code) | Piped review, refactoring, changelog, commit-msg, debug-ci | Anthropic CLI agent |
| [ai-codex/](ai-codex/) | [OpenAI Codex](https://openai.com/index/openai-codex/) | Autonomous coding, sandbox mode, full-auto implement | OpenAI CLI agent |
| [ai-copilot/](ai-copilot/) | [GitHub Copilot](https://docs.github.com/en/copilot) | `gh copilot explain/suggest`, PR review, `.github/copilot-instructions.md` | VS Code + GitHub |
| [ai-cursor/](ai-cursor/) | [Cursor](https://cursor.com) | `.cursor/rules`, Composer context, test-watch, pre-commit | Cursor IDE |
| [ai-windsurf/](ai-windsurf/) | [Windsurf](https://windsurf.com) | `.windsurfrules`, Cascade workflows (`// turbo`), 4 workflow templates | Windsurf IDE |
| [ai-gemini-cli/](ai-gemini-cli/) | [Gemini CLI](https://github.com/google-gemini/gemini-cli) | Multimodal review (screenshots!), sandbox, piped review | Google Gemini |

---

## Szybki wybór przykładu

### 🔰 Zaczynam z taskfile?
```bash
cd minimal/
taskfile run test
taskfile run build
```

### 🚀 SaaS ze staging i prod?
```bash
cd saas-app/
taskfile --env local run dev
taskfile --env staging run deploy
taskfile --env prod run deploy
```

### 📦 Publikuję paczkę Python na PyPI?
```bash
cd publish-pypi/
taskfile auth setup --registry pypi
taskfile run release --var VERSION=1.0.0
```

### 📦 Publikuję paczkę Node.js na npm?
```bash
cd publish-npm/
taskfile auth setup --registry npm
taskfile run release --var VERSION=1.0.0
```

### 📦 Publikuję crate Rust na crates.io?
```bash
cd publish-cargo/
taskfile auth setup --registry crates
taskfile run release --var VERSION=1.0.0
```

### 🐳 Publikuję obraz Docker?
```bash
cd publish-docker/
taskfile run build-multiarch --var TAG=v1.0.0   # amd64 + arm64
```

### 🏷️ Tworzę release na GitHub z binarkami?
```bash
cd publish-github/
taskfile run build-all --var VERSION=1.0.0      # 4 platformy parallel
taskfile run github-release --var VERSION=1.0.0
```

### 🖥️ Web + Desktop aplikacja?
```bash
cd multiplatform/
taskfile --env prod run deploy-all
```

### 🤖 Flota Raspberry Pi / kiosków?
```bash
cd fleet-rpi/
taskfile fleet status                                    # status floty
taskfile -G all-kiosks run deploy-kiosk --var TAG=v2.0   # rolling deploy
taskfile fleet repair kiosk-lobby                        # diagnostyka
```

### 🏭 Monorepo: Python + Rust + Node.js + Docker?
```bash
cd multi-artifact/
taskfile run test-all          # testy 3 języków parallel
taskfile run build-all         # 4 artefakty parallel
taskfile run publish-all       # 5 rejestrów parallel
```

### 🏭 Produkcyjny projekt?
```bash
cd codereview.pl/
taskfile run ci-generate
taskfile --env prod run deploy
```

### 📝 Rozbijam Taskfile na skrypty?
```bash
cd script-extraction/
taskfile run build            # → ./scripts/build.sh
taskfile run release --var TAG=v1.0  # → python scripts/release.py
```

### 🔄 Generuję CI/CD z jednego pliku?
```bash
cd ci-generation/
taskfile ci generate --all    # → 6 platform configs
taskfile ci preview --target github
taskfile ci run               # run pipeline locally
```

### 📦 Rozbijam duży Taskfile na mniejsze pliki?
```bash
cd include-split/
taskfile list                 # tasks from all included files
taskfile run deploy-prod      # from tasks/deploy.yml (prefixed)
taskfile run build            # from tasks/build.yml
```

### 🤖 AI-assisted development z Aider?
```bash
cd ai-aider/
cp .env.example .env          # dodaj ANTHROPIC_API_KEY
taskfile run feature --var PROMPT="Add user authentication"
taskfile run review-diff       # AI review staged changes
taskfile run tdd --var SPEC="Login endpoint returns JWT"
taskfile run lint-fix          # fix linting issues with AI
```

### 🤖 AI-assisted development z Claude Code?
```bash
cd ai-claude-code/
cp .env.example .env           # dodaj ANTHROPIC_API_KEY
taskfile run implement --var PROMPT="Add REST API for users"
taskfile run review-staged     # AI review staged changes
taskfile run generate-tests --var FILE=src/api.py
taskfile run ai-commit         # AI-generated commit message
```

### 🤖 AI-assisted development z Codex?
```bash
cd ai-codex/
cp .env.example .env           # dodaj OPENAI_API_KEY
taskfile run implement --var PROMPT="Add caching layer"
taskfile run implement-auto --var PROMPT="Fix all type errors"
taskfile run sandbox --var PROMPT="Refactor database module"
```

### 🤖 AI-assisted development z Copilot?
```bash
cd ai-copilot/
taskfile run suggest --var PROMPT="deploy to kubernetes"
taskfile run explain --var CMD="git rebase -i HEAD~5"
taskfile run init-instructions  # .github/copilot-instructions.md
```

### 🤖 AI-assisted development z Windsurf?
```bash
cd ai-windsurf/
taskfile run init-rules        # .windsurfrules
taskfile run init-workflows    # .windsurf/workflows/ (4 templates)
# Then use: /add-feature, /fix-bug, /refactor, /doctor
```

### 🤖 AI-assisted development z Gemini CLI?
```bash
cd ai-gemini-cli/
cp .env.example .env           # dodaj GOOGLE_API_KEY
taskfile run implement --var PROMPT="Add search endpoint"
taskfile run review-screenshot --var IMG=ui.png  # multimodal!
taskfile run review-staged
```

---

## Funkcje pokazane w przykładach

### Minimal
- ✅ Podstawowe taski (test, build, run)
- ✅ Zależności (`deps: [test]`)
- ✅ Etapy (`stage: test/build`)

### SaaS App
- ✅ Wielośrodowiskowość (local/staging/prod)
- ✅ SSH deploy (@remote)
- ✅ Pipeline CI/CD
- ✅ Komenda @remote

### Publish (PyPI / npm / Cargo / Docker / GitHub)
- ✅ Pełny pipeline: lint → test → build → publish
- ✅ Dry-run przed publikacją
- ✅ `taskfile auth setup` — konfiguracja tokenów
- ✅ `taskfile auth verify` — weryfikacja tokenów
- ✅ `parallel: true` — równoległe testy i lint
- ✅ `continue_on_error: true` — lint nie blokuje
- ✅ Multi-arch Docker (amd64 + arm64)
- ✅ Checksums SHA256

### Fleet RPi
- ✅ `environment_groups` — grupy urządzeń
- ✅ `strategy: rolling/canary/parallel`
- ✅ `taskfile fleet status` — monitoring floty
- ✅ `taskfile fleet repair` — diagnostyka + auto-fix
- ✅ `taskfile -G <group> run <task>` — deploy na grupę
- ✅ ARM64 build z `docker buildx`

### Multi-Artifact
- ✅ 3 języki (Python + Rust + Node.js) + Docker w jednym repo
- ✅ 5 rejestrów (PyPI, crates.io, npm, GHCR, Docker Hub)
- ✅ `taskfile run test-all` — parallel testy
- ✅ `taskfile run publish-all` — parallel publikacja
- ✅ Wspólna wersja (`--var VERSION=X`)
- ✅ GitHub Releases z binarkami

### Multiplatform
- ✅ Platformy (web/desktop)
- ✅ Auto-generowanie .env
- ✅ Walidacja deploymentu (Docker/VM)
- ✅ Generowanie CI/CD
- ✅ VPS auto-config (VPS_IP)

### Codereview.pl
- ✅ Quadlet generowanie
- ✅ Single source of truth (docker-compose)
- ✅ 6 platform CI/CD
- ✅ Kompletny workflow

---

## Generowanie CI/CD

```bash
taskfile ci generate --platform github
taskfile ci generate --platform gitlab
taskfile ci generate --all
```

## Skrypty testujące

```bash
./run-all.sh              # Uruchom wszystkie przykłady
./run-minimal.sh          # Testuj minimal
./run-saas-app.sh         # Testuj saas-app
./run-multiplatform.sh    # Testuj multiplatform
./run-codereview.sh       # Testuj codereview.pl
```

## Struktura plików

```
examples/
├── README.md
│
│  ─── Basics ───────────────────────────────
├── minimal/                  # ⭐ start here
├── saas-app/                 # ⭐⭐ multi-env (local/staging/prod)
├── multiplatform/            # ⭐⭐⭐ web+desktop × local+prod
├── codereview.pl/            # ⭐⭐⭐⭐ full production project
│
│  ─── Publishing ───────────────────────────
├── publish-pypi/             # 📦 Python → PyPI
├── publish-npm/              # 📦 Node.js → npm
├── publish-cargo/            # 📦 Rust → crates.io
├── publish-docker/           # 🐳 Docker → GHCR + Docker Hub
├── publish-github/           # 🏷️ Go binaries → GitHub Releases
├── multi-artifact/           # 🏭 Python+Rust+Node+Docker monorepo
│
│  ─── Fleet & IoT ──────────────────────────
├── fleet-rpi/                # 🤖 RPi fleet, environment_defaults
├── edge-iot/                 # 📡 IoT gateways, all 3 group strategies
│
│  ─── Infrastructure & Cloud ───────────────
├── ci-pipeline/              # 🔄 pipeline section, ci generate/run
├── kubernetes-deploy/        # ☸️  Helm + multi-cluster K8s
├── iac-terraform/            # 🏗️ Terraform multi-env IaC
├── cloud-aws/                # ☁️  AWS: Lambda + ECS + S3
├── quadlet-podman/           # 🐧 Podman Quadlet → systemd
│
│  ─── Patterns & Import ──────────────────────
├── script-extraction/        # 📝 Taskfile → shell/Python scripts
├── ci-generation/            # 🔄 pipeline → 6 CI platforms
├── include-split/            # 📦 include: import from other YAML files
│
│  ─── Advanced ─────────────────────────────
├── monorepo-microservices/   # 🔧 platforms, condition, dir, stage
├── fullstack-deploy/         # 🎯 ALL CLI commands showcase
│
│  ─── AI Tools ────────────────────────────
├── ai-aider/                 # 🤖 Aider — TDD, review, lint-fix
├── ai-claude-code/           # 🤖 Claude Code — piped review, refactor
├── ai-codex/                 # 🤖 OpenAI Codex — autonomous, sandbox
├── ai-copilot/               # 🤖 GitHub Copilot — explain, suggest, PR
├── ai-cursor/                # 🤖 Cursor — rules, composer, workflows
├── ai-windsurf/              # 🤖 Windsurf — rules, Cascade workflows
├── ai-gemini-cli/            # 🤖 Gemini CLI — multimodal, piped review
│
├── Taskfile.softreck.yml
├── .github-actions-deploy.yml
├── .gitlab-ci.yml
└── .gitea-actions-deploy.yml
```

## Feature Coverage Matrix

| Feature | Example(s) |
|---------|-----------|
| `environments` (multi-env) | saas-app, ci-pipeline, kubernetes-deploy, cloud-aws |
| `environment_defaults` | fleet-rpi, edge-iot, kubernetes-deploy, cloud-aws |
| `environment_groups` (rolling/canary/parallel) | fleet-rpi, edge-iot, kubernetes-deploy, cloud-aws |
| `platforms` + `build_cmd`/`deploy_cmd` | multiplatform, monorepo-microservices |
| `default_platform` | monorepo-microservices |
| `pipeline` section (stages, when, dind) | ci-pipeline, kubernetes-deploy, cloud-aws, monorepo-microservices, fullstack-deploy |
| `stage` field (auto-infer pipeline) | ci-pipeline, iac-terraform, monorepo-microservices |
| `compose` section (override_files, network) | quadlet-podman, monorepo-microservices, fullstack-deploy |
| `service_manager: quadlet` | quadlet-podman, codereview.pl, monorepo-microservices, fullstack-deploy |
| `quadlet_dir` / `quadlet_remote_dir` | quadlet-podman, fullstack-deploy |
| `dir` (working_dir on task) | iac-terraform, monorepo-microservices |
| `condition` on task | ci-pipeline, iac-terraform, cloud-aws, edge-iot, monorepo-microservices |
| `silent` on task | ci-pipeline, cloud-aws, quadlet-podman, fullstack-deploy |
| `ignore_errors` / `continue_on_error` | all publish-*, ci-pipeline, iac-terraform |
| `parallel` (deps run concurrently) | multi-artifact, monorepo-microservices, publish-github |
| `env_file` per environment | ci-pipeline, iac-terraform, cloud-aws, edge-iot, quadlet-podman, fullstack-deploy |
| `ssh_port` (non-standard) | edge-iot (2200), quadlet-podman (2222) |
| `@remote` SSH commands | fleet-rpi, edge-iot, quadlet-podman, saas-app, codereview.pl |
| `--var KEY=VALUE` override | all examples |
| `--dry-run` | fullstack-deploy |
| `taskfile ci generate/run/preview/list` | ci-pipeline, fullstack-deploy |
| `taskfile deploy` (auto strategy) | quadlet-podman, fullstack-deploy |
| `taskfile setup` (VPS provisioning) | quadlet-podman, fullstack-deploy |
| `taskfile validate/info/list` | fullstack-deploy |
| `include` (import from files) | include-split |
| Script extraction (shell/Python) | script-extraction |
| SSH embedded (paramiko) | saas-app, fleet-rpi, edge-iot (when `pip install taskfile[ssh]`) |
| AI code review | ai-aider, ai-claude-code, ai-codex, ai-copilot, ai-gemini-cli |
| AI test generation | ai-aider, ai-claude-code, ai-codex, ai-gemini-cli |
| AI commit messages | ai-claude-code, ai-copilot, ai-gemini-cli |
| AI lint/type fix | ai-aider, ai-codex |
| IDE rules generation | ai-cursor (`.cursor/rules`), ai-windsurf (`.windsurfrules`), ai-copilot (`.github/copilot-instructions.md`) |
| IDE workflow templates | ai-windsurf (`.windsurf/workflows/`), ai-cursor (Composer) |
| AI TDD cycle | ai-aider (`tdd` task) |
| Multimodal review | ai-gemini-cli (screenshots, diagrams) |
| Sandbox/safe mode | ai-codex (`--sandbox`), ai-gemini-cli (`--sandbox`) |
| `taskfile doctor` + AI | ai-aider, ai-claude-code, ai-codex, ai-gemini-cli (`doctor-ai` task) |

---

## Best Practices: Kod vs Konfiguracja

Te przykłady stosują następujące zasady. Stosuj je w swoich Taskfile:

### 1. Taskfile.yml = deklaratywna konfiguracja

```yaml
# ✅ Krótkie, jednoliniowe komendy
tasks:
  build:
    deps: [test]
    cmds:
      - cargo build --release
```

```yaml
# ❌ Logika bash wewnątrz YAML
tasks:
  build:
    cmds:
      - |
        if [ "$ENV" = "prod" ]; then
          cargo build --release
        else
          cargo build
        fi
```

### 2. `@local`/`@remote` zamiast if-else i duplikatów

```yaml
# ❌ Osobne taski: logs + logs-remote
logs:
  env: [local]
  cmds: [docker compose logs -f]
logs-remote:
  env: [prod]
  cmds: ["@remote podman logs app -f"]
```

```yaml
# ✅ Jeden task z @local/@remote
logs:
  env: [local, prod]
  cmds:
    - "@local ${COMPOSE} logs -f"
    - "@remote podman logs app -f"
```

Patrz: [saas-app/](saas-app/), [codereview.pl/](codereview.pl/)

### 3. `${COMPOSE}` zamiast hardcoded `docker compose --env-file`

```yaml
# ❌ Powtórzenie w każdym tasku
dev:
  cmds: [docker compose --env-file .env.local up -d]
logs:
  cmds: [docker compose --env-file .env.local logs -f]
status:
  cmds: [docker compose --env-file .env.local ps]
```

```yaml
# ✅ ${COMPOSE} automatycznie używa compose_command + env_file z environment
environments:
  local:
    compose_command: docker compose
    env_file: .env.local
tasks:
  dev:
    cmds: [${COMPOSE} up -d]
  logs:
    cmds: [${COMPOSE} logs -f]
```

Patrz: [codereview.pl/](codereview.pl/), [saas-app/](saas-app/)

### 4. Skrypty shell → `scripts/`

Gdy task wymaga ifów, pętli, error handling — wyciągnij do pliku:

```yaml
# ✅ Taskfile woła skrypt
ci-generate:
  cmds:
    - ./scripts/ci-generate.sh
```

Patrz: [multiplatform/scripts/](multiplatform/scripts/)

### 5. `environment_defaults` zamiast kopiowania

```yaml
# ✅ DRY — 2 linie na urządzenie
environment_defaults:
  ssh_user: pi
  ssh_key: ~/.ssh/fleet
  container_runtime: podman

environments:
  node-1:
    ssh_host: 192.168.1.10
  node-2:
    ssh_host: 192.168.1.11
```

Patrz: [fleet-rpi/](fleet-rpi/)

### 6. Nie deklaruj `environments` bez potrzeby

```yaml
# ✅ Publish pipeline nie potrzebuje environments
version: "1"
name: my-lib
variables:
  VERSION: "1.0.0"
tasks:
  test:
    cmds: [cargo test]
  publish:
    deps: [test]
    cmds: [cargo publish]
```

Patrz: [publish-pypi/](publish-pypi/), [publish-cargo/](publish-cargo/), [publish-npm/](publish-npm/)

### 7. `deps` + `parallel` zamiast powtarzania komend

```yaml
# ✅ Compose tasks via deps
test-all:
  deps: [py-test, rs-test, js-test]
  parallel: true
```

Patrz: [multi-artifact/](multi-artifact/)

---

## Jak zacząć?

1. **Wybierz przykład** pasujący do Twojego projektu
2. **Skopiuj Taskfile.yml** do swojego projektu
3. **Dostosuj zmienne** (APP_NAME, REGISTRY, etc.)
4. **Skonfiguruj tokeny**: `taskfile auth setup`
5. **Uruchom pierwszy task**: `taskfile list`

## Wsparcie

- [Główny README](../README.md) — pełna dokumentacja + integracja z Make/Just/Task/Dagger/Ansible
- [Dokumentacja](../docs/)
- [CHANGELOG](../CHANGELOG.md)
