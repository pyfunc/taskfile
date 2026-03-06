# Taskfile REST API

REST API for executing and managing Taskfile tasks over HTTP.

## Quick Start

```bash
# Install API dependencies
pip install taskfile[api]

# Start server
taskfile api serve

# Or directly with uvicorn
uvicorn taskfile.api:app --reload --port 8000
```

**Interactive docs:** http://localhost:8000/docs (Swagger UI) | http://localhost:8000/redoc (ReDoc)

## Server Options

```bash
taskfile api serve                    # Default: 0.0.0.0:8000
taskfile api serve -p 3000            # Custom port
taskfile api serve --reload           # Auto-reload (dev mode)
taskfile api serve --no-browser       # Don't open browser
taskfile api serve --host 127.0.0.1   # Bind to localhost only

# Export OpenAPI spec
taskfile api openapi                  # Print to stdout
taskfile api openapi -o openapi.json  # Save to file

# Use specific Taskfile
taskfile -f /path/to/Taskfile.yml api serve
```

---

## Endpoints

### Health

```bash
# Health check
curl http://localhost:8000/health
```

```json
{
  "status": "ok",
  "version": "0.3.46",
  "taskfile_found": true,
  "taskfile_path": "/home/user/project/Taskfile.yml",
  "task_count": 12,
  "env_count": 3
}
```

---

### Taskfile Configuration

```bash
# Full Taskfile as JSON
curl http://localhost:8000/taskfile

# With specific path
curl "http://localhost:8000/taskfile?path=/path/to/Taskfile.yml"
```

```bash
# Global variables
curl http://localhost:8000/variables
```

```json
{"APP": "myapp", "TAG": "latest", "REGISTRY": "ghcr.io/org"}
```

```bash
# JSON Schema for Taskfile.yml
curl http://localhost:8000/schema
```

---

### Tasks

```bash
# List all tasks
curl http://localhost:8000/tasks

# Filter by environment
curl "http://localhost:8000/tasks?env=prod"

# Filter by platform
curl "http://localhost:8000/tasks?platform=web"

# Filter by tag
curl "http://localhost:8000/tasks?tag=ci"

# Get task details
curl http://localhost:8000/tasks/deploy
```

**Response:**
```json
{
  "name": "deploy",
  "description": "Deploy to environment",
  "commands": ["@local ${COMPOSE} up -d", "@remote podman pull ${IMAGE}:${TAG}"],
  "deps": ["build"],
  "env_filter": ["local", "prod"],
  "platform_filter": null,
  "tags": ["deploy"],
  "stage": "deploy",
  "retries": 0,
  "timeout": 0,
  "has_condition": false
}
```

---

### Run Tasks

```bash
# Run a single task
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{"tasks": ["build"]}'

# Run with environment
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{"tasks": ["deploy"], "env": "prod"}'

# Run with variable overrides
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{"tasks": ["build", "deploy"], "env": "prod", "variables": {"TAG": "v1.2.3"}}'

# Dry run (preview without executing)
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{"tasks": ["deploy"], "dry_run": true}'

# Run with platform
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{"tasks": ["deploy"], "env": "prod", "platform": "web"}'

# Run with tag filter
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{"tasks": ["build", "test"], "tags": ["ci"]}'
```

**Response:**
```json
{
  "success": true,
  "tasks": [
    {
      "task": "build",
      "status": "success",
      "duration_ms": 1234,
      "output": ["Building myapp:v1.2.3..."],
      "error": null
    },
    {
      "task": "deploy",
      "status": "success",
      "duration_ms": 5678,
      "output": ["Deploying to prod..."],
      "error": null
    }
  ],
  "total_duration_ms": 6912,
  "env": "prod",
  "dry_run": false
}
```

---

### Validate

```bash
# Validate current Taskfile
curl -X POST http://localhost:8000/validate \
  -H "Content-Type: application/json" \
  -d '{}'

# Validate specific file
curl -X POST http://localhost:8000/validate \
  -H "Content-Type: application/json" \
  -d '{"path": "/path/to/Taskfile.yml"}'
```

```json
{
  "valid": true,
  "warnings": [],
  "task_count": 12,
  "env_count": 3
}
```

---

### Doctor (Diagnostics)

Run 5-layer diagnostics on the production server — same as `taskfile doctor` but over HTTP.

```bash
# Quick health check (GET — read-only, no fixes)
curl http://localhost:8000/doctor

# Verbose mode (extra checks: task commands, SSH, remote health)
curl "http://localhost:8000/doctor?verbose=true"

# Filter by category
curl "http://localhost:8000/doctor?category=config"
```

```json
{
  "total_issues": 3,
  "errors": 2,
  "warnings": 0,
  "info": 1,
  "auto_fixable": 0,
  "fixed_count": 0,
  "healthy": false,
  "summary": "Errors: 2, Info: 1",
  "issues": [
    {
      "category": "dependency_missing",
      "message": "podman: not found (optional)",
      "severity": "info",
      "fix_strategy": "manual",
      "auto_fixable": false,
      "layer": 1,
      "fix_description": "Install: apt install podman  # https://podman.io/docs/installation",
      "teach": "Podman is a Docker alternative..."
    }
  ],
  "categories": { "dependency_missing": [...], "external_error": [...] },
  "llm_suggestions": []
}
```

```bash
# Run with auto-fix + LLM suggestions (POST)
curl -X POST http://localhost:8000/doctor \
  -H "Content-Type: application/json" \
  -d '{"fix": true, "llm": true}'

# Verbose + specific category
curl -X POST http://localhost:8000/doctor \
  -H "Content-Type: application/json" \
  -d '{"verbose": true, "category": "runtime"}'
```

**POST body options:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `fix` | bool | `false` | Apply Layer 4 algorithmic fixes |
| `verbose` | bool | `false` | Extra checks (task commands, SSH, remote health) |
| `category` | string | `"all"` | Filter: `config`, `env`, `infra`, `runtime`, or `all` |
| `llm` | bool | `false` | Ask AI for suggestions (Layer 5, requires `taskfile[llm]`) |

---

### Environments

```bash
# List all environments
curl http://localhost:8000/environments

# Get environment details
curl http://localhost:8000/environments/prod
```

```json
{
  "name": "prod",
  "ssh_host": "prod.example.com",
  "ssh_user": "deploy",
  "ssh_port": 22,
  "container_runtime": "podman",
  "compose_command": "docker compose",
  "service_manager": "quadlet",
  "env_file": ".env.prod",
  "is_remote": true
}
```

---

### Environment Groups

```bash
# List fleet groups
curl http://localhost:8000/groups
```

```json
[
  {
    "name": "kiosks",
    "members": ["kiosk1", "kiosk2", "kiosk3"],
    "strategy": "rolling",
    "max_parallel": 2,
    "canary_count": 1
  }
]
```

---

### Platforms

```bash
curl http://localhost:8000/platforms
```

---

### Functions

```bash
curl http://localhost:8000/functions
```

```json
[
  {
    "name": "notify-slack",
    "lang": "python",
    "description": "Send Slack notification",
    "has_code": true,
    "has_file": false
  }
]
```

---

### Pipeline

```bash
curl http://localhost:8000/pipeline
```

```json
[
  {"name": "test", "tasks": ["test"], "env": null, "when": "auto"},
  {"name": "build", "tasks": ["build"], "env": null, "when": "auto"},
  {"name": "deploy", "tasks": ["deploy-quick"], "env": "prod", "when": "manual"}
]
```

---

## Error Handling

All errors return JSON with `detail` field:

```json
{"detail": "Task 'nonexistent' not found. Available: build, deploy, test"}
```

| Status | Meaning |
|--------|---------|
| `200` | Success |
| `404` | Taskfile or task not found |
| `422` | Validation error (bad request body or Taskfile parse error) |
| `500` | Internal server error |

---

## CORS

The API allows all origins by default (for development). Configure CORS in production by modifying `create_app()` in `src/taskfile/api/app.py`.

---

## Python Client Example

```python
import httpx

api = "http://localhost:8000"

# List tasks
tasks = httpx.get(f"{api}/tasks").json()
for t in tasks:
    print(f"{t['name']}: {t['description']}")

# Run a task
result = httpx.post(f"{api}/run", json={
    "tasks": ["build", "deploy"],
    "env": "prod",
    "variables": {"TAG": "v1.2.3"},
}).json()

if result["success"]:
    print(f"Done in {result['total_duration_ms']}ms")
else:
    for t in result["tasks"]:
        if t["status"] == "failed":
            print(f"FAILED: {t['task']}: {t['error']}")

# Doctor — run diagnostics on production server
doctor = httpx.get(f"{api}/doctor", params={"verbose": True}).json()
if doctor["healthy"]:
    print("Server is healthy!")
else:
    print(f"Issues: {doctor['summary']}")
    for issue in doctor["issues"]:
        print(f"  [{issue['severity']}] {issue['message']}")

# Doctor with auto-fix
doctor = httpx.post(f"{api}/doctor", json={"fix": True, "verbose": True}).json()
print(f"Fixed: {doctor['fixed_count']}, Remaining: {doctor['total_issues']}")
```

---

## JavaScript/fetch Example

```javascript
// List tasks
const tasks = await fetch("http://localhost:8000/tasks").then(r => r.json());

// Run task
const result = await fetch("http://localhost:8000/run", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    tasks: ["deploy"],
    env: "prod",
    variables: { TAG: "v1.2.3" },
  }),
}).then(r => r.json());

// Doctor — production health check
const doctor = await fetch("http://localhost:8000/doctor?verbose=true").then(r => r.json());
console.log(doctor.healthy ? "Healthy" : `Issues: ${doctor.summary}`);

// Doctor with auto-fix
const fixed = await fetch("http://localhost:8000/doctor", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ fix: true, verbose: true }),
}).then(r => r.json());
console.log(`Fixed: ${fixed.fixed_count}, Remaining: ${fixed.total_issues}`);
```
