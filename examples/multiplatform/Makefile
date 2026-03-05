# Multiplatform Example - Makefile
.PHONY: all test list validate help

export PYTHONPATH := /home/tom/github/pyfunc/taskfile/src:$(PYTHONPATH)

all: test

# Test the example (validation and listing)
test:
	@echo "═══════════════════════════════════════════════════════════════"
	@echo "  Multiplatform Example (Desktop + Web)"
	@echo "═══════════════════════════════════════════════════════════════"
	@echo ""
	@echo "▶ Validating Taskfile..."
	@python3 -c "from taskfile.parser import load_taskfile, validate_taskfile; c=load_taskfile('Taskfile.yml'); validate_taskfile(c)"
	@echo "✅ Validation passed"
	@echo ""
	@echo "📋 Environments:"
	@python3 -c "from taskfile.parser import load_taskfile; c=load_taskfile('Taskfile.yml'); [print(f'  - {n}: {e.container_runtime}') for n,e in c.environments.items()]"
	@echo ""
	@echo "📋 Platforms:"
	@python3 -c "from taskfile.parser import load_taskfile; c=load_taskfile('Taskfile.yml'); [print(f'  - {n}: {p.description}') for n,p in c.platforms.items()]"
	@echo ""
	@echo "📋 Tasks:"
	@python3 -c "from taskfile.parser import load_taskfile; c=load_taskfile('Taskfile.yml'); [print(f'  - {n}: {t.description or \"No desc\"}') for n,t in c.tasks.items()]"
	@echo ""
	@echo "✅ Multiplatform example test completed"

# Quick validation only
validate:
	@python3 -c "from taskfile.parser import load_taskfile, validate_taskfile; c=load_taskfile('Taskfile.yml'); validate_taskfile(c); print('✅ Valid')"

# List tasks
list:
	@python3 -c "from taskfile.parser import load_taskfile; c=load_taskfile('Taskfile.yml'); [print(f'  - {n}: {t.description or \"No desc\"}') for n,t in c.tasks.items()]"

# List for specific matrix combination
list-matrix:
	@echo "📋 Matrix combinations:"
	@python3 -c "from taskfile.parser import load_taskfile; c=load_taskfile('Taskfile.yml'); \
		[print(f'  - {n} (env={t.env_filter}, platform={t.platform_filter})') for n,t in c.tasks.items() if t.env_filter or t.platform_filter]"

# Help
help:
	@echo "Multiplatform Example - Available targets:"
	@echo ""
	@echo "  make test        - Run all tests (dry-run)"
	@echo "  make validate    - Validate Taskfile only"
	@echo "  make list        - List available tasks"
	@echo "  make list-matrix - List tasks for matrix combinations"
	@echo "  make help        - Show this help"
