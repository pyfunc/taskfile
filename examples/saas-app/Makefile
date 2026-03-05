# SaaS App Example - Makefile
.PHONY: all test list validate help

export PYTHONPATH := /home/tom/github/pyfunc/taskfile/src:$(PYTHONPATH)

all: test

# Test the example (validation and listing)
test:
	@echo "═══════════════════════════════════════════════════════════════"
	@echo "  SaaS App Example"
	@echo "═══════════════════════════════════════════════════════════════"
	@echo ""
	@echo "▶ Validating Taskfile..."
	@python3 -c "from taskfile.parser import load_taskfile, validate_taskfile; c=load_taskfile('Taskfile.yml'); validate_taskfile(c)"
	@echo "✅ Validation passed"
	@echo ""
	@echo "📋 Environments:"
	@python3 -c "from taskfile.parser import load_taskfile; c=load_taskfile('Taskfile.yml'); [print(f'  - {n}: {e.container_runtime}') for n,e in c.environments.items()]"
	@echo ""
	@echo "📋 Tasks:"
	@python3 -c "from taskfile.parser import load_taskfile; c=load_taskfile('Taskfile.yml'); [print(f'  - {n}: {t.description or \"No desc\"}') for n,t in c.tasks.items()]"
	@echo ""
	@echo "📋 Pipeline stages:"
	@python3 -c "from taskfile.parser import load_taskfile; c=load_taskfile('Taskfile.yml'); [print(f'  - {s.name}: {s.tasks}') for s in c.pipeline.stages]"
	@echo ""
	@echo "✅ SaaS App example test completed"

# Quick validation only
validate:
	@python3 -c "from taskfile.parser import load_taskfile, validate_taskfile; c=load_taskfile('Taskfile.yml'); validate_taskfile(c); print('✅ Valid')"

# List tasks
list:
	@python3 -c "from taskfile.parser import load_taskfile; c=load_taskfile('Taskfile.yml'); [print(f'  - {n}: {t.description or \"No desc\"}') for n,t in c.tasks.items()]"

# List for specific environment
list-local:
	@python3 -c "from taskfile.parser import load_taskfile; c=load_taskfile('Taskfile.yml'); print('Tasks for local env:'); [print(f'  - {n}: {t.description or \"No desc\"}') for n,t in c.tasks.items() if not t.env_filter or 'local' in t.env_filter]"

# Help
help:
	@echo "SaaS App Example - Available targets:"
	@echo ""
	@echo "  make test        - Run all tests (dry-run)"
	@echo "  make validate    - Validate Taskfile only"
	@echo "  make list        - List available tasks"
	@echo "  make list-local  - List tasks for local environment"
	@echo "  make help        - Show this help"
