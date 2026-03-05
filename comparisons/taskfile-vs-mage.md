# Taskfile vs Mage

## Quick Comparison

| Feature | Mage | Taskfile |
|---------|------|----------|
| Tasks in code | ✅ (Go) | ❌ (YAML) |
| Type safety | ✅ | ❌ |
| Cross-compilation | ✅ | ⚠️ |
| **YAML simplicity** | ❌ | ✅ |
| **Environments** | ❌ | ✅ |
| **SSH remote execution** | ❌ | ✅ (`@remote`) |
| **Fleet management** | ❌ | ✅ |
| **Registry authentication** | ❌ | ✅ |
| **Quadlet generation** | ❌ | ✅ |
| **VPS setup** | ❌ | ✅ |
| **CI/CD generation** | ❌ | ✅ |
| **Learning curve** | Medium | Low |

## What is Mage?

Mage is a build tool where tasks are written in Go code instead of shell scripts. It uses Go's type system and standard library.

**Key strengths:**
- Tasks in Go code (not YAML/shell)
- Type-safe task definitions
- Cross-compilation support
- Go standard library available
- Native Go tooling (testing, debugging)
- Fast execution (compiled)

## When to Use Mage

- Go-centric projects
- Teams comfortable with Go
- Need type-safe task definitions
- Complex logic that benefits from Go
- Cross-compilation requirements
- Want to avoid YAML/shell

## When to Use Taskfile Instead

- Non-Go teams
- YAML preference
- Multi-environment deployments
- SSH-based remote execution
- Fleet management needed
- Registry authentication
- Podman Quadlet generation
- VPS provisioning
- Quick setup and iteration

## Side-by-Side Examples

### Basic Task

```go
// magefile.go
//go:build mage

package main

import (
    "fmt"
    "os/exec"
)

// Build builds the application
func Build() error {
    cmd := exec.Command("go", "build", "-o", "myapp", ".")
    return cmd.Run()
}

// Test runs all tests
func Test() error {
    cmd := exec.Command("go", "test", "./...")
    return cmd.Run()
}
```

```yaml
# Taskfile.yml
tasks:
  build:
    cmds:
      - go build -o myapp .
  
  test:
    cmds:
      - go test ./...
```

### Variables

```go
// magefile.go
var (
    image = "myapp"
    tag   = "latest"
)

// Build builds the container image
func Build() error {
    cmd := exec.Command("docker", "build", "-t", image+":"+tag, ".")
    return cmd.Run()
}
```

```yaml
# Taskfile.yml
variables:
  IMAGE: myapp
  TAG: latest

tasks:
  build:
    cmds:
      - docker build -t ${IMAGE}:${TAG} .
```

### Dependencies

```go
// magefile.go
import "github.com/magefile/mage/mg"

// Deploy deploys the application (depends on Build)
func Deploy() error {
    mg.Deps(Build)
    
    // Deploy logic here
    cmd := exec.Command("docker", "push", image+":"+tag)
    return cmd.Run()
}

// BuildAndTest runs both (parallel)
func BuildAndTest() {
    mg.Deps(Build, Test)
}
```

```yaml
# Taskfile.yml
tasks:
  build:
    cmds:
      - go build -o myapp .
  
  test:
    cmds:
      - go test ./...
  
  deploy:
    deps: [build]
    cmds:
      - docker push ${IMAGE}:${TAG}
  
  build-and-test:
    deps: [build, test]
    parallel: true
```

### Remote Execution (SSH)

Mage has no built-in SSH abstraction — you write Go code:

```go
// magefile.go
import (
    "golang.org/x/crypto/ssh"
)

func DeployProd() error {
    config := &ssh.ClientConfig{
        User: "deploy",
        Auth: []ssh.AuthMethod{
            ssh.PublicKeysFile("~/.ssh/id_ed25519"),
        },
        HostKeyCallback: ssh.InsecureIgnoreHostKey(),
    }
    
    client, err := ssh.Dial("tcp", "prod.example.com:22", config)
    if err != nil {
        return err
    }
    defer client.Close()
    
    session, err := client.NewSession()
    if err != nil {
        return err
    }
    defer session.Close()
    
    return session.Run("podman pull myapp:latest && systemctl restart myapp")
}
```

```yaml
# Taskfile.yml - Simple @remote
environments:
  prod:
    ssh_host: prod.example.com
    ssh_user: deploy

tasks:
  deploy:
    env: [prod]
    cmds:
      - "@remote podman pull ${IMAGE}:${TAG}"
      - "@remote systemctl --user restart ${APP}"
```

### Fleet Deploy

Mage requires custom Go code for fleet management:

```go
// magefile.go
var kiosks = []struct {
    host string
    user string
}{
    {"192.168.1.10", "pi"},
    {"192.168.1.11", "pi"},
    {"192.168.1.12", "pi"},
}

func DeployKiosks() error {
    for _, kiosk := range kiosks {
        if err := deployToHost(kiosk.host, kiosk.user); err != nil {
            return err
        }
    }
    return nil
}

func deployToHost(host, user string) error {
    // SSH logic here...
    return nil
}
```

```yaml
# Taskfile.yml - Built-in fleet management
environments:
  kiosk1: {ssh_host: 192.168.1.10, ssh_user: pi}
  kiosk2: {ssh_host: 192.168.1.11, ssh_user: pi}
  kiosk3: {ssh_host: 192.168.1.12, ssh_user: pi}

environment_groups:
  kiosks:
    members: [kiosk1, kiosk2, kiosk3]
    strategy: rolling
    max_parallel: 2

tasks:
  deploy:
    cmds:
      - "@remote podman pull ${IMAGE}:${TAG}"
      - "@remote systemctl --user restart ${APP}"
```

Usage:
```bash
# Deploy to all kiosks with rolling strategy
taskfile -G kiosks run deploy --var TAG=v1.0

# Fleet status
taskfile fleet status --group kiosks
```

## Key Differences

### Mage's Advantages
1. **Type safety** - Go compiler catches errors
2. **Go standard library** - Full power of Go available
3. **Testing** - Write tests for your tasks
4. **Cross-compilation** - Build for any platform
5. **Debugging** - Use Go debugger
6. **IDE support** - Auto-completion, refactoring
7. **Compiled speed** - Fast execution
8. **No YAML** - Code instead of configuration

### Taskfile's Advantages
1. **Simplicity** - YAML is universally understood
2. **Low learning curve** - No Go knowledge needed
3. **SSH execution** - Native `@remote` support
4. **Environments** - Abstract deployment targets
5. **Fleet management** - Groups, rolling deploys
6. **Registry auth** - Interactive token setup
7. **Quadlet generation** - docker-compose → systemd
8. **VPS setup** - One-command provisioning
9. **CI/CD generation** - GitHub Actions, GitLab CI
10. **Fleet commands** - `status`, `repair`, `list`

## Migration from Mage to Taskfile

### When to Migrate

Consider migrating when:
- Team doesn't know Go
- YAML is preferred
- Need fleet management
- Want built-in SSH abstraction
- Need registry/VPS integration

### How to Migrate

**1. Convert Go functions to YAML tasks**

```go
// magefile.go
func Build() error {
    cmd := exec.Command("go", "build", "-o", "app", ".")
    return cmd.Run()
}
```

```yaml
# Taskfile.yml
tasks:
  build:
    cmds:
      - go build -o app .
```

**2. Convert Go variables to YAML**

```go
var image = "myapp"
var tag = "latest"
```

```yaml
variables:
  IMAGE: myapp
  TAG: latest
```

**3. Add environments for SSH targets**

```go
// Mage SSH code (complex)
```

```yaml
# Taskfile environments (simple)
environments:
  prod:
    ssh_host: prod.example.com
    ssh_user: deploy

tasks:
  deploy:
    cmds:
      - "@remote podman pull ${IMAGE}:${TAG}"
```

## Can They Coexist?

Yes! Use Mage for complex Go logic and Taskfile for deployment:

```go
// magefile.go
// Complex build logic in Go
func Build() error {
    // Custom Go build logic
    return nil
}

func Test() error {
    // Custom test logic
    return nil
}

// Simple wrapper to call taskfile
func Deploy() error {
    cmd := exec.Command("taskfile", "--env", "prod", "run", "deploy")
    return cmd.Run()
}
```

```yaml
# Taskfile.yml
environments:
  prod:
    ssh_host: prod.example.com
    ssh_user: deploy

tasks:
  build:
    cmds:
      - mage build  # Call Mage for build
  
  deploy:
    deps: [build]
    cmds:
      - "@remote podman pull ${IMAGE}:${TAG}"
      - "@remote systemctl --user restart ${APP}"
```

## Summary

| Use Case | Recommendation |
|----------|----------------|
| Go-centric team | Mage ✅ |
| Type-safe tasks | Mage ✅ |
| Complex Go logic | Mage ✅ |
| Cross-compilation | Mage ✅ |
| YAML preference | Taskfile ✅ |
| Non-Go team | Taskfile ✅ |
| Multi-environment deploys | Taskfile ✅ |
| SSH remote execution | Taskfile ✅ |
| Fleet management | Taskfile ✅ |
| Registry/VPS integration | Taskfile ✅ |
| Quick setup | Taskfile ✅ |

## Verdict

**Choose Mage if:**
- Your team is Go-centric
- You need type-safe task definitions
- Complex logic benefits from Go
- Cross-compilation is required

**Choose Taskfile if:**
- YAML is preferred
- Team doesn't know Go
- Multi-environment deployments
- SSH/fleet features needed
- Registry/VPS integration required
- Faster setup time needed

**They can coexist:**

```
Mage → Complex builds, Go logic, type safety
Taskfile → Deployments, SSH, fleet, registry
```
