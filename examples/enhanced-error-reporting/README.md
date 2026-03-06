# Enhanced Error Reporting Example

This example demonstrates the new error reporting and diagnostic features added to taskfile:

## Features Demonstrated

### 1. Placeholder Detection (`check_placeholder_values`)

The Taskfile uses placeholder patterns that will be detected:

```yaml
ssh_host: ${STAGING_HOST:-staging.example.com}  # ⚠️ Will warn about placeholder
ssh_host: ${PROD_HOST:-your-server.example.com}  # ⚠️ Placeholder pattern detected!
```

Run `taskfile doctor` to see placeholder warnings with `--teach` for explanations.

### 2. Pre-run Validation (`--explain` and `--teach` modes)

Preview what will happen without executing:

```bash
taskfile run deploy --env staging --explain
```

See educational explanations of @local/@remote behavior:

```bash
taskfile run deploy --env local --teach
```

### 3. @local/@remote Skip Messages

The `deploy` task demonstrates environment-specific command filtering:

```yaml
tasks:
  deploy:
    cmds:
      - "@local docker compose build"   # Skipped on remote envs (with message)
      - "@remote docker compose up -d"  # Skipped on local envs (with message)
```

You'll see explicit skip messages like:
- `⏭ Pominięto @local (env 'staging' jest zdalny — ma ssh_host)`
- `⏭ Pominięto @remote (env 'local' nie ma ssh_host)`

### 4. Rich Error Diagnosis (ErrorPresenter)

When commands fail, you get contextual diagnosis:

```bash
taskfile run build  # If scripts/build.sh is missing
```

Shows:
- Clear error category (Config vs Runtime vs External)
- Root cause analysis
- Fix suggestions with commands
- Educational explanation of the underlying concept

### 5. Layered Doctor Output with `teach` Field

Run with educational mode:

```bash
taskfile doctor --teach
```

Output shows 3 layers:
- **⚙️ Konfiguracja** - Taskfile.yml issues, missing files, placeholders
- **📦 Zależności** - Missing tools (docker, ssh, etc.)
- **🔧 Runtime** - Port conflicts, SSH issues, disk space

Each issue includes a `teach` explanation when `--teach` is used.

## Try It Out

### 1. Check for issues (with educational explanations)

```bash
cd examples/enhanced-error-reporting
taskfile doctor --teach
```

You'll see:
- Placeholder warnings for `your-server.example.com`
- Missing `.env.*` file warnings
- Missing `scripts/build.sh` warning

### 2. Preview execution plan

```bash
taskfile run deploy --explain
```

Shows:
- Which commands will run for current env
- Which will be skipped (@local/@remote filtering)
- Dependencies in execution order

### 3. Learn about @local/@remote

```bash
taskfile run deploy --teach
```

Explains:
- What @local means (only runs when env has NO ssh_host)
- What @remote means (only runs when env HAS ssh_host)
- Which commands run in which environments

### 4. Create required files and re-check

```bash
# Create missing files
cp .env.example .env.local 2>/dev/null || echo "APP_NAME=myapp" > .env.local
mkdir -p scripts
echo '#!/bin/bash\necho "Building..."' > scripts/build.sh

# Re-run doctor - should have fewer issues
taskfile doctor
```

## New Issue Types with `teach` Field

All these checks now include educational explanations:

| Check | Issue | `teach` Explanation |
|-------|-------|---------------------|
| `check_preflight` | Missing python3, git, ssh | Why each tool is needed |
| `check_ssh_keys` | No ~/.ssh or keys | SSH authentication basics |
| `check_ssh_connectivity` | Connection refused, auth failed | SSH debugging steps |
| `check_ports` | Port in use | How port binding works |
| `check_placeholder_values` | example.com, changeme, etc. | What placeholders are |
| `check_git` | Not a git repo | Why version control matters |
| `check_dependent_files` | Missing script | script: vs cmds: difference |

## Key Success Metric

> After an error, the user knows in 5 seconds what went wrong, if it's config or bug, and how to fix it.

Try running a task that will fail:

```bash
taskfile run build  # Will fail - scripts/build.sh doesn't exist
```

The error output will show:
1. **What**: Script not found
2. **Why**: The 'script:' directive requires an external file
3. **Fix**: Create the file OR use 'cmds:' with inline commands
4. **Learn**: Difference between script: and cmds: approaches
