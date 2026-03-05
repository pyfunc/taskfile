# Minimal Example - Makefile
.PHONY: all test validate list help

export PYTHONPATH := /home/tom/github/pyfunc/taskfile/src:$(PYTHONPATH)

all: test

# Test the example (validation and listing)
test:
	@echo "═══════════════════════════════════════════════════════════════"
	@echo "  Minimal Example"
	@echo "═══════════════════════════════════════════════════════════════"
	@echo ""
	@echo "▶ Validating Taskfile..."
	@python3 -c "from taskfile.parser import load_taskfile, validate_taskfile; c=load_taskfile('Taskfile.yml'); validate_taskfile(c)"
	@echo "✅ Validation passed"
	@echo ""
	@echo "📋 Tasks:"
	@python3 -c "from taskfile.parser import load_taskfile; c=load_taskfile('Taskfile.yml'); [print(f'  - {n}: {t.description or \"No desc\"}') for n,t in c.tasks.items()]"
	@echo ""
	@echo "✅ Minimal example test completed"

# Quick validation only
validate:
	@python3 -c "from taskfile.parser import load_taskfile, validate_taskfile; c=load_taskfile('Taskfile.yml'); validate_taskfile(c); print('✅ Valid')"

# List tasks
list:
	@python3 -c "from taskfile.parser import load_taskfile; c=load_taskfile('Taskfile.yml'); [print(f'  - {n}: {t.description or \"No desc\"}') for n,t in c.tasks.items()]"

# Help
help:
	@echo "Minimal Example - Available targets:"
	@echo ""
	@echo "  make test      - Run all tests (dry-run)"
	@echo "  make validate  - Validate Taskfile only"
	@echo "  make list      - List available tasks"
	@echo "  make help      - Show this help"
