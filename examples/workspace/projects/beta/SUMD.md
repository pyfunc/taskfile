# beta

Demo project beta — missing common tasks (lint, build)

## Contents

- [Metadata](#metadata)
- [Architecture](#architecture)
- [Workflows](#workflows)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Intent](#intent)

## Metadata

- **name**: `beta`
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
  name: "beta";
  version: "0.1.0";
}

workflow[name="install"] {
  trigger: "manual";
  step-1: run cmd=echo "beta: install";
}

workflow[name="test"] {
  trigger: "manual";
  step-1: run cmd=echo "beta: test";
}
```

## Workflows

### Taskfile Tasks (`Taskfile.yml`)

```yaml markpact:taskfile path=Taskfile.yml
version: '1'
name: beta

tasks:
  install:
    desc: Install dependencies
    cmds:
    - echo "beta: install"

  test:
    desc: Run tests
    cmds:
    - echo "beta: test"
```

## Configuration

```yaml
project:
  name: beta
  version: 0.1.0
  env: local
```

## Deployment

```bash markpact:run
pip install beta

# development install
pip install -e .[dev]
```

## Intent

Demo project beta — missing common tasks (lint, build)
