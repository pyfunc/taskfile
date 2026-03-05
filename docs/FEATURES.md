# Taskfile Features Guide

Detailed documentation of taskfile features and capabilities.

## 🎯 Core Features

### Multi-Environment Support

Deploy to different environments with the same Taskfile:

```yaml
environments:
  local:
    container_runtime: docker
    compose_command: docker compose
  
  staging:
    ssh_host: ${STAGING_HOST}
    ssh_user: deploy
    container_runtime: podman
  
  prod:
    ssh_host: ${PROD_HOST}
    ssh_user: deploy
    container_runtime: podman
    service_manager: quadlet
```

Run with environment:
```bash
taskfile run deploy --env prod
```

### SSH Remote Execution

Execute commands on remote hosts:

```yaml
tasks:
  deploy:
    cmds:
      - "@remote docker pull myapp:latest"
      - "@remote systemctl restart myapp"
```

Or configure SSH globally:
```yaml
environments:
  prod:
    ssh_host: server.example.com
    ssh_user: deploy
    ssh_key: ~/.ssh/id_ed25519
```

### Dependency Management

Define task dependencies:

```yaml
tasks:
  test:
    deps: [lint, build]
    cmds:
      - pytest
  
  deploy:
    deps: [test]
    cmds:
      - docker push myapp
```

Run dependencies in parallel:
```yaml
tasks:
  build-all:
    deps: [build-web, build-api, build-worker]
    parallel: true
```

## 🎨 Interactive Features

### Doctor Command

Auto-diagnose project issues:

```bash
taskfile doctor           # Check project health
taskfile doctor --fix     # Auto-fix issues
```

Checks for:
- Taskfile.yml validity
- Missing .env files
- Required tools (Docker, SSH)
- Missing API keys

### Interactive Setup

Guided configuration:

```bash
taskfile setup env        # Configure .env with prompts
```

Features:
- LLM provider selection (OpenRouter, OpenAI, Anthropic, Ollama, Groq)
- API key input with helpful links
- Port configuration
- Project name

```bash
taskfile setup hosts      # Configure deployment hosts
```

Interactive prompts for:
- Staging host
- Production host
- Deploy user

### Auto-Suggest

Fuzzy matching for typos:

```bash
$ taskfile run bould
✗ Unknown task: bould
  Did you mean: build, build-web, build-all?
```

## 👁️ Development Features

### Watch Mode

Auto-rebuild on changes:

```bash
taskfile watch build              # Watch current directory
taskfile watch -p src build       # Watch specific path
taskfile watch -d 500 build       # 500ms debounce
```

Features:
- Automatic file detection
- Configurable debounce
- Ignore patterns (.git, node_modules, etc.)
- Multiple path support

### Smart Cache

Skip unchanged tasks:

```bash
taskfile cache show       # View cache statistics
taskfile cache clear      # Clear all cache
taskfile cache clear build  # Clear specific task cache
```

Cache mechanism:
- Tracks input file hashes
- Caches command outputs
- Invalidates on file changes
- Stores in `~/.cache/taskfile/`

### Progress Bars

Visual feedback for long tasks:

```
▶ build — Building application
  → docker build -t myapp .
  ↻ Building... 15.2s
```

Features:
- Rich spinners
- Time elapsed
- Task descriptions
- Transient display (clears after completion)

### Desktop Notifications

Alerts when tasks complete:

```bash
taskfile run deploy  # Shows notification after completion (>10s)
```

Supported platforms:
- macOS (osascript)
- Linux (notify-send/zenity)
- Windows (PowerShell)

## 📦 Ecosystem Features

### Package Registry

Install and share tasks:

```bash
# Search for packages
taskfile pkg search docker

# Install from GitHub
taskfile pkg install user/docker-tasks

# List installed
taskfile pkg list

# Uninstall
taskfile pkg uninstall docker-tasks
```

Packages installed to `~/.taskfile/registry/packages/`

### Import/Export

Convert from/to other formats:

```bash
# Import
taskfile import Makefile
taskfile import .github/workflows/ci.yml --type github-actions
taskfile import package.json --type npm

# Export
taskfile export makefile -o Makefile
taskfile export github-actions -o .github/workflows/ci.yml
taskfile export npm --project-name my-app
```

### Task Graph

Visualize dependencies:

```bash
taskfile graph                    # Show all dependencies
taskfile graph build              # Show build task graph
taskfile graph --dot              # Export to Graphviz DOT
taskfile graph --dot -o graph.dot # Save to file
```

Generate image:
```bash
taskfile graph --dot -o tasks.dot && dot -Tpng -o tasks.png tasks.dot
```

## 🌐 Web Features

### Web Dashboard

Browser-based task management:

```bash
taskfile serve              # Start on port 8080
taskfile serve -p 3000     # Custom port
taskfile serve --no-browser # Don't auto-open
```

Features:
- Task listing with search
- Environment filtering
- One-click task execution
- Real-time output display
- Statistics dashboard

Access at `http://localhost:8080`

## 🔧 Advanced Features

### Embedded Functions

Define reusable functions:

```yaml
functions:
  notify:
    lang: python
    code: |
      import os
      print(f"[notify] {os.environ.get('FN_ARGS')}")
  
  health-check:
    lang: shell
    code: |
      URL="${1:-http://localhost:8000/health}"
      curl -sf "$URL" && echo "OK" || echo "FAIL"

tasks:
  deploy:
    cmds:
      - "@fn notify Deployment starting"
      - docker-compose up -d
      - "@fn health-check http://server/health"
```

### Variable Substitution

Multiple syntax options:

```yaml
variables:
  VERSION: "1.0.0"

tasks:
  build:
    cmds:
      - echo "Version is {{VERSION}}"    # Jinja style
      - echo "Version is ${VERSION}"   # Shell style
      - echo "Version is $VERSION"       # Simple style
```

Environment variables:
```yaml
variables:
  API_KEY: ${API_KEY}                    # Required
  DEBUG: ${DEBUG:-false}                 # With default
```

### Conditional Execution

Skip tasks based on conditions:

```yaml
tasks:
  deploy:
    condition: "${DEPLOY_ENABLED} == true"
    cmds:
      - echo "Deploying..."
```

### Error Handling

Retry failed tasks:

```yaml
tasks:
  deploy:
    retries: 3
    retry_delay: 10
    cmds:
      - docker push myapp
```

Ignore errors:
```yaml
tasks:
  cleanup:
    ignore_errors: true
    cmds:
      - docker rm old_container  # May not exist
```

Timeout:
```yaml
tasks:
  test:
    timeout: 300  # 5 minutes
    cmds:
      - pytest
```

### Parallel Execution

Fleet deployment strategies:

```yaml
environment_groups:
  kiosks:
    strategy: parallel
    max_parallel: 5
    members: [kiosk-01, kiosk-02, ...]
```

Run with:
```bash
taskfile -G kiosks run deploy
```

Strategies:
- `rolling` — One at a time, wait between
- `canary` — First N, then rest after confirmation
- `parallel` — All at once (configurable limit)

### Tag-Based Execution

Selective task running:

```yaml
tasks:
  unit-test:
    tags: [test, quick]
    cmds: [pytest -m unit]
  
  integration-test:
    tags: [test, slow]
    cmds: [pytest -m integration]
```

Run with tags:
```bash
taskfile run --tags quick test  # Run only quick tests
```

## 🎨 UX Features

### Shell Completion

Tab completion for:
- Task names
- Environment names
- Platform names
- File paths

Setup:
```bash
# Bash
eval "$(taskfile --completion bash)"

# Zsh
eval "$(taskfile --completion zsh)"

# Fish
taskfile --completion fish > ~/.config/fish/completions/taskfile.fish
```

### Nearby Taskfile Detection

When no Taskfile found, suggests nearby ones:

```bash
$ taskfile list
Error: No Taskfile found

📍 Found Taskfiles in nearby directories:
   ./sandbox/Taskfile.yml (1 level down)
   ../Taskfile.yml (1 level up)

To use:
  cd sandbox && taskfile run <task>
```

### Rich Error Messages

Helpful error context:

```bash
$ taskfile run bould
✗ Unknown task: bould
  Did you mean: build, build-web, build-all?

Available tasks: build, test, deploy, lint, clean, ...
```

---

## Configuration Files

### taskfile.json

Track installed packages:

```json
{
  "dependencies": {
    "user/docker-tasks": "latest",
    "org/k8s-deploy": "v1.2.0"
  }
}
```

### ~/.taskfile/

User data directory:
```
~/.taskfile/
├── registry/
│   ├── cache/          # Downloaded packages
│   └── packages/       # Installed packages
└── config.yml         # Global settings
```

---

Last updated: 2024-03-05
