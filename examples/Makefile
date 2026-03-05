# Taskfile Examples - Makefile
# Run individual examples or all at once

.PHONY: all minimal saas-app multiplatform codereview test clean help

# Python path for taskfile module
export PYTHONPATH := /home/tom/github/pyfunc/taskfile/src:$(PYTHONPATH)

# Default target
all: test

# Run all examples
test: minimal saas-app multiplatform codereview
	@echo ""
	@echo "✅ All examples completed successfully!"

# Individual examples
minimal:
	@echo "═══════════════════════════════════════════════════════════════"
	@echo "  Running: Minimal Example"
	@echo "═══════════════════════════════════════════════════════════════"
	@cd minimal && $(MAKE) test

saas-app:
	@echo "═══════════════════════════════════════════════════════════════"
	@echo "  Running: SaaS App Example"
	@echo "═══════════════════════════════════════════════════════════════"
	@cd saas-app && $(MAKE) test

multiplatform:
	@echo "═══════════════════════════════════════════════════════════════"
	@echo "  Running: Multiplatform Example"
	@echo "═══════════════════════════════════════════════════════════════"
	@cd multiplatform && $(MAKE) test

codereview:
	@echo "═══════════════════════════════════════════════════════════════"
	@echo "  Running: codereview.pl Example"
	@echo "═══════════════════════════════════════════════════════════════"
	@cd codereview.pl && $(MAKE) test

# Using shell scripts directly
test-sh:
	@bash run-all.sh

minimal-sh:
	@bash run-minimal.sh

saas-app-sh:
	@bash run-saas-app.sh

multiplatform-sh:
	@bash run-multiplatform.sh

codereview-sh:
	@bash run-codereview.sh

# Validation only (no execution)
validate:
	@echo "Validating all examples..."
	@cd minimal && python3 -c "from taskfile.parser import load_taskfile, validate_taskfile; c=load_taskfile('Taskfile.yml'); validate_taskfile(c); print('✅ minimal')"
	@cd saas-app && python3 -c "from taskfile.parser import load_taskfile, validate_taskfile; c=load_taskfile('Taskfile.yml'); validate_taskfile(c); print('✅ saas-app')"
	@cd multiplatform && python3 -c "from taskfile.parser import load_taskfile, validate_taskfile; c=load_taskfile('Taskfile.yml'); validate_taskfile(c); print('✅ multiplatform')"
	@cd codereview.pl && python3 -c "from taskfile.parser import load_taskfile, validate_taskfile; c=load_taskfile('Taskfile.yml'); validate_taskfile(c); print('✅ codereview.pl')"
	@echo ""
	@echo "✅ All examples validated successfully!"

# List examples
list:
	@echo "Available examples:"
	@echo "  minimal       - Simplest possible Taskfile (test, build, run)"
	@echo "  saas-app      - Multi-environment SaaS deployment"
	@echo "  multiplatform - Desktop (Electron) + Web (Docker)"
	@echo "  codereview.pl - Real-world production deployment"

# Help
help:
	@echo "Taskfile Examples - Available targets:"
	@echo ""
	@echo "  make test          - Run all examples (default)"
	@echo "  make minimal       - Run minimal example"
	@echo "  make saas-app      - Run saas-app example"
	@echo "  make multiplatform - Run multiplatform example"
	@echo "  make codereview    - Run codereview.pl example"
	@echo ""
	@echo "  make validate      - Validate all Taskfiles (no execution)"
	@echo "  make list          - List available examples"
	@echo "  make help          - Show this help"
	@echo ""
	@echo "Alternative (shell scripts):"
	@echo "  make test-sh       - Run all via run-all.sh"
	@echo "  make minimal-sh    - Run minimal via shell script"
	@echo "  ..."

clean:
	@echo "Nothing to clean"
