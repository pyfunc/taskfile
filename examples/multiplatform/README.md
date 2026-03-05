# Taskfile - Advanced Usage Guide

## Jak działa Taskfile

Taskfile to **universal task runner** który pozwala zdefiniować zadania raz i uruchamiać je wszędzie:
- Lokalnie (Docker Compose)
- Produkcja (VPS przez SSH)
- CI/CD (GitHub Actions, GitLab CI, Jenkins)

### Architektura

```
┌────────────────────────────────────────────────────────┐
│                    Taskfile.yml                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Variables   │  │Environments  │  │  Platforms   │  │
│  │  (zmienne)   │  │  (envs)      │  │              │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│  ┌───────────────────────────────────────────────────┐ │
│  │                  Tasks                            │ │
│  │  - init    - deploy    - ci-generate              │ │
│  │  - build   - validate  - test                     │ │
│  │  - push    - status    - logs                     │ │
│  └───────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────┘
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    ┌────────────┐  ┌────────────┐  ┌────────────┐
    │   Local    │  │    VPS     │  │   CI/CD    │
    │  Docker    │  │   SSH      │  │  GitHub    │
    └────────────┘  └────────────┘  └────────────┘
```

## Co można zrobić z Taskfile

### 1. Generowanie plików CI/CD

```bash
# Generuj pliki dla różnych platform CI/CD
taskfile run ci-generate

# Powstaną:
# .github/workflows/deploy.yml  (GitHub Actions)
# .gitlab-ci.yml                (GitLab CI)
```

**Jak to działa:**
Task `ci-generate` tworzy gotowe konfiguracje które:
- Instalują taskfile w runnerze CI
- Używają tych samych komend co lokalnie (`taskfile run deploy`)
- Pobierają VPS_IP/VPS_USER z secrets

### 2. Walidacja deploymentu (Docker/VM)

```bash
# Walidacja w izolowanym kontenerze
taskfile run validate-deploy

# Walidacja w VM (Vagrant)
taskfile run validate-vm

# Pełna walidacja (Docker + testy)
taskfile run validate-all

# Sprawdzenie wymagań przed deploy
taskfile run preflight
```

**Jak to działa:**

**validate-deploy**:
1. Buduje obraz Docker: `docker build -t app-validate`
2. Uruchamia kontener na porcie 9999
3. Wykonuje health check: `curl http://localhost:9999/health`
4. Sprząta: zatrzymuje i usuwa kontener

**validate-vm**:
1. Tworzy Vagrantfile (Ubuntu VM)
2. Instaluje Podman w VM
3. Deployuje przez SSH do VM
4. Testuje na `http://localhost:9999`

### 3. Deploy na VPS (automatyczny)

```bash
# Setup VPS (instalacja Podman, firewall)
taskfile --env prod run vps-setup

# Deploy web
taskfile --env prod --platform web run deploy

# Deploy desktop + web
taskfile --env prod run deploy-all
```

**Jak to działa:**

```
Twoja maszyna          VPS (przez SSH)
      │                       │
      ├── ssh VPS_IP ────────►│
      │                       │
      ├── docker build        │
      ├── docker push ───────►│ podman pull
      │                       │
      └── ssh restart ───────►│ podman run
```

### 4. Auto-generowanie .env

```bash
# Tworzy .env z .env.example
taskfile run init

# Sprawdza konfigurację
taskfile run env-check
```

## Przykłady użycia

### Szybki start (nowy projekt)

```bash
# 1. Clone repo
git clone https://github.com/example/app.git
cd app

# 2. Init (stworzy .env)
taskfile run init

# 3. Edytuj .env
nano .env
# VPS_IP=123.456.789.012

# 4. Walidacja
taskfile run validate-all

# 5. Deploy
taskfile --env prod run deploy-all
```

### Workflow deweloperski

```bash
# Lokalny development
taskfile run dev              # Start lokalnie
taskfile run test             # Uruchom testy
taskfile run preflight        # Sprawdź czy wszystko OK

# Generuj CI/CD
taskfile run ci-generate
git add .github/workflows/
git commit -m "Add CI/CD"

# Deploy na VPS
taskfile --env prod run deploy-all
```

### Integracja z CI/CD

**GitHub Actions** (auto-generowany):
```yaml
name: Deploy
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install taskfile
      - run: taskfile --env prod run deploy
        env:
          VPS_IP: ${{ secrets.VPS_IP }}
```

**GitLab CI** (auto-generowany):
```yaml
stages:
  - deploy

deploy:
  stage: deploy
  script:
    - pip install taskfile
    - taskfile --env prod run deploy
  only:
    - main
```

## Kluczowe funkcje

| Funkcja | Opis | Komenda |
|---------|------|---------|
| **Multi-env** | local/prod z różnymi konfiguracjami | `--env prod` |
| **Multi-platform** | web/desktop z różnymi deployami | `--platform web` |
| **Variables** | Kaskadowe zmienne: global → env → platform → CLI | `--var KEY=value` |
| **@remote** | Prefix dla komend SSH | `@remote podman ps` |
| **deps** | Zależności między taskami | `deps: [init, build]` |
| **condition** | Warunkowe wykonanie | `condition: "test -f file"` |
| **Dry-run** | Podgląd bez wykonania | `--dry-run` |

## Struktura zmiennych

```yaml
variables:
  # Global (domyślne dla wszystkich)
  APP_NAME: my-app
  TAG: latest

environments:
  local:
    variables:
      DOMAIN: localhost        # Nadpisuje dla local
  
  prod:
    variables:
      DOMAIN: ${VPS_IP}        # Nadpisuje dla prod

# CLI nadpisuje wszystko:
# taskfile --env prod --var TAG=v1.0.0 run deploy
```

## Jak taskfile działa wewnętrznie

1. **Parse**: Wczytuje Taskfile.yml
2. **Resolve**: Oblicza zmienne (global → env → platform → CLI)
3. **Filter**: Wybiera taski pasujące do `--env` i `--platform`
4. **Execute**: Uruchamia komendy:
   - `@remote` → wykonuje przez SSH
   - `deps: []` → uruchamia zależności pierwsze
   - `ignore_errors: true` → kontynuuje mimo błędu

## Walidacja deploymentu - szczegóły

### Opcja 1: Docker (najszybsza)

```bash
taskfile run validate-deploy
```

Co się dzieje:
```
Docker Build ──► Docker Run ──► Health Check ──► Cleanup
     │               │              │               │
  30s-2m        Start app      curl /health    docker rm
```

### Opcja 2: Vagrant VM (najbliższa produkcji)

```bash
taskfile run validate-vm
```

Co się dzieje:
```
Vagrant Up ──► Install Podman ──► Deploy ──► Test ──► Destroy
    │              │                │          │         │
  2-5 min       apt-get        Same as      curl    vagrant
                                prod         /health  destroy
```

### Opcja 3: Staging environment

```yaml
# Dodaj staging do Taskfile.yml
environments:
  staging:
    ssh_host: staging.example.com
    container_runtime: podman
```

```bash
taskfile --env staging run deploy
```

## Rozszerzanie Taskfile

### Dodanie nowego providera CI/CD

```yaml
# W task ci-generate
ci-generate:
  cmds:
    - |
      # Jenkins
      cat > Jenkinsfile << 'EOF'
      pipeline {
        agent any
        stages {
          stage('Deploy') {
            steps {
              sh 'pip install taskfile'
              sh 'taskfile --env prod run deploy'
            }
          }
        }
      }
      EOF
```

### Dodanie nowego środowiska

```yaml
environments:
  staging:
    desc: Staging environment
    ssh_host: ${STAGING_IP}
    ssh_user: deploy
    container_runtime: podman
    variables:
      DOMAIN: staging.example.com
```

```bash
taskfile --env staging run deploy
```

## Podsumowanie

Taskfile pozwala:
1. ✅ **Jedna konfiguracja** → działa lokalnie, na VPS i w CI/CD
2. ✅ **Walidacja przed deploy** → Docker lub VM
3. ✅ **Auto-generowanie** → .env, CI/CD files
4. ✅ **Szybki deploy** → wystarczy IP VPS + SSH key

**Minimalny setup**:
```bash
echo "VPS_IP=123.456.789.012" > .env
taskfile --env prod run deploy-all
```
