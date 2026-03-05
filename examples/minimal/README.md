# Minimal Taskfile Example

Najprostszy możliwy Taskfile - idealny na początek.

## Czym jest ten przykład?

Ten przykład pokazuje minimalną konfigurację Taskfile bez:
- Środowisk (environments)
- SSH/deploy na VPS
- Platform (web/desktop)

## Struktura

```
minimal/
├── Taskfile.yml    # Definicja tasków
├── Makefile        # Dla porównania (stary sposób)
└── README.md       # Ten plik
```

## Taski

| Task | Opis | Zależności |
|------|------|------------|
| `test` | Uruchom testy (pytest) | - |
| `build` | Zbuduj obraz Docker | test |
| `run` | Uruchom lokalnie | - |

## Użycie

```bash
# Zainstaluj taskfile
pip install taskfile

# Zobacz dostępne taski
taskfile list

# Uruchom testy
taskfile run test

# Zbuduj (automatycznie uruchomi testy pierwsze)
taskfile run build

# Uruchom aplikację
taskfile run run
```

## Jak to działa

### Zależności (deps)

```yaml
build:
  deps: [test]    # Najpierw uruchomi `test`, potem build
```

### Stage (etapy)

```yaml
test:
  stage: test     # Grupa tasków
build:
  stage: build    # Można uruchomić wszystkie z etapu
```

## Porównanie z Makefile

**Makefile**:
```makefile
test:
	pytest -v

build: test
	docker build -t my-app:latest .
```

**Taskfile**:
```yaml
test:
  desc: Run tests
  stage: test
  cmds:
    - pytest -v

build:
  desc: Build Docker image
  stage: build
  deps: [test]
  cmds:
    - docker build -t my-app:latest .
```

## Kiedy użyć minimalnego Taskfile?

✅ Projekty lokalne (bez VPS)  
✅ Szybki start z taskfile  
✅ Proste CI/CD bez deploy na serwer  

## Następne kroki

Zobacz inne przykłady:
- [saas-app/](../saas-app/) - Deploy na staging + prod
- [multiplatform/](../multiplatform/) - Web + Desktop
- [codereview.pl/](../codereview.pl/) - Kompletny projekt z pipeline
