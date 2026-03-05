# Taskfile Examples

Kompletne przykłady użycia Taskfile dla różnych scenariuszy.

## Przegląd przykładów

| Przykład | Złożoność | Cechy | Kiedy użyć |
|----------|-----------|-------|------------|
| [minimal/](minimal/) | ⭐ Najniższa | Podstawowe taski, bez środowisk | Projekty lokalne, start z taskfile |
| [saas-app/](saas-app/) | ⭐⭐ Niska | local/staging/prod, pipeline | SaaS z wieloma env |
| [multiplatform/](multiplatform/) | ⭐⭐⭐ Średnia | Web + Desktop, walidacja, CI/CD gen | Aplikacje multi-platform |
| [codereview.pl/](codereview.pl/) | ⭐⭐⭐⭐ Wysoka | Full CI/CD, 6 platform, Quadlet | Real-world produkcyjne |

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

### 🖥️ Web + Desktop aplikacja?
```bash
cd multiplatform/
taskfile --env prod run deploy-all  # SaaS + Desktop
```

### 🏭 Produkcyjny projekt?
```bash
cd codereview.pl/
taskfile run ci-generate  # Generuj CI/CD
taskfile --env prod run deploy
```

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

## Generowanie CI/CD

Wszystkie przykłady (oprócz minimal) pokazują generowanie CI/CD:

```bash
# Multiplatform
taskfile run ci-generate

# Codereview.pl
taskfile ci generate --all
taskfile ci generate --platform github
taskfile ci generate --platform gitlab
```

## Walidacja

```bash
# Multiplatform - walidacja w Docker
taskfile run validate-deploy

# Multiplatform - walidacja w VM
taskfile run validate-vm

# Multiplatform - sprawdzenie wymagań
taskfile run preflight
```

## Skrypty testujące

W głównym katalogu `examples/` znajdują się skrypty do testowania:

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
├── README.md              # Ten plik
├── minimal/
│   ├── Taskfile.yml
│   ├── Makefile
│   └── README.md
├── saas-app/
│   ├── Taskfile.yml
│   ├── Makefile
│   └── README.md
├── multiplatform/
│   ├── Taskfile.yml
│   └── README.md
├── codereview.pl/
│   ├── Taskfile.yml
│   ├── docker-compose.yml
│   ├── .env.local
│   ├── .env.prod
│   └── README.md
├── Taskfile.softreck.yml  # Multi-project
├── .github-actions-deploy.yml
├── .gitlab-ci.yml
└── .gitea-actions-deploy.yml
```

## Taskfile.softreck.yml

Specjalny przykład multi-project deploymentu dla organizacji Softreck:
- wronai
- prototypowanie
- portigen

## CI/CD Templates

Gotowe szablony dla różnych platform:

- `.github-actions-deploy.yml` - GitHub Actions
- `.gitlab-ci.yml` - GitLab CI
- `.gitea-actions-deploy.yml` - Gitea Actions

## Jak zacząć?

1. **Wybierz przykład** pasujący do Twojego projektu
2. **Skopiuj Taskfile.yml** do swojego projektu
3. **Dostosuj zmienne** (APP_NAME, REGISTRY, etc.)
4. **Uruchom pierwszy task**: `taskfile list`

## Wsparcie

Więcej informacji w głównej dokumentacji:
- [Główny README](../README.md)
- [Dokumentacja](../docs/)
- [CHANGELOG](../CHANGELOG.md)

