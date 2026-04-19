# alpha

Demo project alpha — fully in sync

## Contents

- [Metadata](#metadata)
- [Architecture](#architecture)
- [Workflows](#workflows)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Intent](#intent)

## Metadata

- **name**: `alpha`
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
  name: "alpha";
  version: "0.1.0";
}

workflow[name="install"] {
  trigger: "manual";
  step-1: run cmd=echo "alpha: install";
}

workflow[name="test"] {
  trigger: "manual";
  step-1: run cmd=echo "alpha: test";
}

workflow[name="lint"] {
  trigger: "manual";
  step-1: run cmd=echo "alpha: lint";
}

workflow[name="build"] {
  trigger: "manual";
  step-1: run cmd=echo "alpha: build";
}
```

## Workflows

### Taskfile Tasks (`Taskfile.yml`)

```yaml markpact:taskfile path=Taskfile.yml
version: '1'
name: alpha

tasks:
  install:
    desc: Install dependencies
    cmds:
    - echo "alpha: install"

  test:
    desc: Run tests
    cmds:
    - echo "alpha: test"

  lint:
    desc: Lint
    cmds:
    - echo "alpha: lint"

  build:
    desc: Build artifact
    cmds:
    - echo "alpha: build"
```

## Configuration

```yaml
project:
  name: alpha
  version: 0.1.0
  env: local
```

## Deployment

```bash markpact:run
pip install alpha

# development install
pip install -e .[dev]
```

## Intent

Demo project alpha — fully in sync
