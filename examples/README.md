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

### Zaawansowane

| Przykład | Złożoność | Cechy | Kiedy użyć |
|----------|-----------|-------|------------|
| [fleet-rpi/](fleet-rpi/) | ⭐⭐⭐⭐ | 6 RPi, 3 grupy, rolling/canary | Flota IoT/kiosków |
| [multi-artifact/](multi-artifact/) | ⭐⭐⭐⭐⭐ | Python+Rust+Node+Docker → 5 rejestrów | Monorepo multi-język |

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
├── minimal/               # ⭐ start
├── saas-app/              # ⭐⭐ multi-env
├── multiplatform/         # ⭐⭐⭐ web+desktop
├── codereview.pl/         # ⭐⭐⭐⭐ full project
├── publish-pypi/          # 📦 Python → PyPI
├── publish-npm/           # 📦 Node.js → npm
├── publish-cargo/         # 📦 Rust → crates.io
├── publish-docker/        # 🐳 Docker → GHCR + Docker Hub
├── publish-github/        # 🏷️ Binaries → GitHub Releases
├── fleet-rpi/             # 🤖 RPi fleet management
├── multi-artifact/        # 🏭 Python+Rust+Node+Docker monorepo
├── Taskfile.softreck.yml
├── .github-actions-deploy.yml
├── .gitlab-ci.yml
└── .gitea-actions-deploy.yml
```

## Jak zacząć?

1. **Wybierz przykład** pasujący do Twojego projektu
2. **Skopiuj Taskfile.yml** do swojego projektu
3. **Dostosuj zmienne** (APP_NAME, REGISTRY, etc.)
4. **Skonfiguruj tokeny**: `taskfile auth setup`
5. **Uruchom pierwszy task**: `taskfile list`

## Wsparcie

Więcej informacji w głównej dokumentacji:
- [Główny README](../README.md)
- [Dokumentacja](../docs/)
- [CHANGELOG](../CHANGELOG.md)

## License

Apache License 2.0 - see [LICENSE](LICENSE) for details.

## Author

Created by **Tom Sapletta** - [tom@sapletta.com](mailto:tom@sapletta.com)
