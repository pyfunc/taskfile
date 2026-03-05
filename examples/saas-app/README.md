# SaaS App Example

SaaS aplikacja z deploy na staging i produkcję.

## Wbudowane środowiska

```
┌─────────┐     ┌──────────┐     ┌─────────┐
│  local  │────▶│ staging  │────▶│  prod   │
│ (dev)   │     │ (test)   │     │ (live)  │
└─────────┘     └──────────┘     └─────────┘
```

## Konfiguracja środowisk

```yaml
environments:
  local:
    container_runtime: docker
    env_file: .env.local

  staging:
    ssh_host: staging.myapp.com
    container_runtime: podman
    env_file: .env.staging

  prod:
    ssh_host: prod.myapp.com
    container_runtime: podman
    env_file: .env.prod
```

## Pipeline CI/CD

```yaml
pipeline:
  stages:
    - test        # lint, test
    - build       # build, push
    - deploy-staging    # auto deploy
    - deploy-prod       # manual approve
```

## Taski

| Task | Środowisko | Opis |
|------|------------|------|
| `lint` | all | Sprawdź kod (ruff) |
| `test` | all | Uruchom testy |
| `build` | all | Zbuduj obrazy |
| `push` | all | Wyślij do registry |
| `deploy` | staging, prod | Deploy na VPS |
| `dev` | local | Start lokalny |
| `status` | staging, prod | Status serwera |

## Użycie

```bash
# Lokalny development
taskfile --env local run dev

# Deploy na staging (automatyczny przez CI)
taskfile --env staging run deploy

# Deploy na produkcję (manualny)
taskfile --env prod run deploy

# Sprawdź status produkcji
taskfile --env prod run status
```

## Workflow CI/CD

### Lokalnie
```bash
taskfile run lint
taskfile run test
taskfile run build
```

### Staging (automatyczny)
```bash
git push origin main
# CI automatycznie uruchomi: taskfile --env staging run deploy
```

### Produkcja (manualny)
```bash
# W CI/CD kliknij "Deploy to Production"
# Lub lokalnie:
taskfile --env prod run deploy
```

## Zmienne środowiskowe

```bash
# .env.local
REGISTRY=ghcr.io/myorg
TAG=latest

# .env.staging / .env.prod
REGISTRY=ghcr.io/myorg
TAG=stable
```

## Komenda @remote

Deploy używa prefixu `@remote` do wykonania komend na VPS:

```yaml
deploy:
  cmds:
    - "@remote podman pull ${REGISTRY}/saas-app:${TAG}"
    - "@remote systemctl --user restart saas-app"
```

## Kiedy użyć tego przykładu?

✅ SaaS aplikacje z wieloma środowiskami  
✅ Staging → Production workflow  
✅ Automatyczne CI/CD z manualnym approve  

## Następne kroki

Zobacz inne przykłady:
- [multiplatform/](../multiplatform/) - Web + Desktop
- [codereview.pl/](../codereview.pl/) - Pełny pipeline
