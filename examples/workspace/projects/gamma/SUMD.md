# gamma

Demo project gamma — has sync issues (tasks without workflows)

## Contents

- [Metadata](#metadata)
- [Architecture](#architecture)
- [Workflows](#workflows)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Intent](#intent)

## Metadata

- **name**: `gamma`
- **version**: `0.1.0`
- **ecosystem**: SUMD + DOQL + testql + taskfile
- **generated_from**: pyproject.toml, Taskfile.yml, app.doql.css

## Architecture

```
SUMD (description) → DOQL/source (code) → taskfile (automation) → testql (verification)
```

### DOQL Application Declaration (`app.doql.css`)

```css markpact:doql path=app.doql.css
app {
  name: "gamma";
  version: "0.1.0";
}

workflow[name="install"] {
  trigger: "manual";
  step-1: run cmd=echo "gamma: install";
}

workflow[name="test"] {
  trigger: "manual";
  step-1: run cmd=echo "gamma: test";
}

workflow[name="legacy-release"] {
  trigger: "manual";
  step-1: run cmd=echo "gamma: legacy-release";
}
```

## Workflows

### Taskfile Tasks (`Taskfile.yml`)

```yaml markpact:taskfile path=Taskfile.yml
version: '1'
name: gamma

tasks:
  install:
    desc: Install dependencies
    cmds:
    - echo "gamma: install"

  test:
    desc: Run tests
    cmds:
    - echo "gamma: test"

  lint:
    desc: Lint
    cmds:
    - echo "gamma: lint"

  build:
    desc: Build
    cmds:
    - echo "gamma: build"

  deploy:
    desc: Deploy (no matching workflow in doql — sync issue!)
    cmds:
    - echo "gamma: deploy"
```

## Configuration

```yaml
project:
  name: gamma
  version: 0.1.0
  env: local
```

## Deployment

```bash markpact:run
pip install gamma

# development install
pip install -e .[dev]
```

## Intent

Demo project gamma — has sync issues (tasks without workflows)
