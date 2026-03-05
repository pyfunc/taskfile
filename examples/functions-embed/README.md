# Example: Embedded Functions

Demonstrates the `functions` section — embed Python, shell, Node.js, or binary tools as callable functions from task commands using the `@fn` prefix.

## Features Shown

- **`functions` section** — define reusable functions in multiple languages
- **`@fn` prefix** — call functions from task commands
- **`@python` prefix** — run inline Python directly
- **`retries` + `retry_delay`** — automatic retry on failure (Ansible-inspired)
- **`timeout`** — command timeout in seconds
- **`tags`** — selective task execution with `--tags`
- **`register`** — capture command stdout into a variable

## Function Types

| Type | `lang` | Source | Example |
|------|--------|--------|---------|
| Inline shell | `shell` | `code:` block | `check-port` |
| Inline Python | `python` | `code:` block | `notify` |
| Python file | `python` | `file:` path | `generate-report` |
| Shell file | `shell` | `file:` path | `health-check` |
| Inline Node.js | `node` | `code:` block | `render-config` |
| Binary/tool | `binary` | `file:` path | `lint-yaml` |

## Usage

```bash
# List tasks
taskfile list

# Call function via task
taskfile run status              # → @fn check-port 8080
taskfile run config              # → @fn render-config (Node.js)
taskfile run report              # → @fn generate-report (Python file)

# Inline Python
taskfile run inline-python       # → @python import os; print(...)

# Deploy with notifications
taskfile run deploy              # → @fn notify, @fn health-check

# Full deploy with retries + timeout
taskfile run full-deploy         # retries=2, timeout=300s

# Capture output into variable
taskfile run capture-version     # register: APP_VERSION

# Run only tasks tagged 'ci'
taskfile run build test deploy --tags ci
```

## Syntax Reference

### Defining Functions

```yaml
functions:
  my-func:
    lang: python          # shell | python | node | binary
    desc: Description
    code: |               # inline code
      print("hello")
    # OR
    file: scripts/tool.py # external file
    function: main        # specific Python function (optional)
```

### Calling Functions

```yaml
tasks:
  example:
    cmds:
      - "@fn my-func arg1 arg2"    # call defined function
      - "@python print('hello')"   # inline Python (no function needed)
```

### Task Attributes (Ansible-inspired)

```yaml
tasks:
  robust-deploy:
    retries: 3          # retry failed commands up to 3 times
    retry_delay: 10     # wait 10s between retries
    timeout: 600        # abort after 600s
    tags: [deploy, ci]  # filter with --tags
    register: OUTPUT    # capture stdout into $OUTPUT variable
```
