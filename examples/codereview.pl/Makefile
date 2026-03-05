# Auto-generated from Taskfile.yml — do not edit manually
# Regenerate with: taskfile ci generate --target makefile

ENV ?= local
TAG ?= latest

.PHONY: help
help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

.PHONY: build
build: ## Build all images
	taskfile --env $(ENV) run build --var TAG=$(TAG)

.PHONY: build-app
build-app: ## Build single service (--var SVC=app)
	taskfile --env $(ENV) run build-app --var TAG=$(TAG)

.PHONY: cleanup
cleanup: ## Clean unused images/volumes on production
	taskfile --env $(ENV) run cleanup --var TAG=$(TAG)

.PHONY: deploy
deploy: ## Full deploy: generate Quadlet → upload → pull → restart
	taskfile --env $(ENV) run deploy --var TAG=$(TAG)

.PHONY: deploy-quick
deploy-quick: ## Quick deploy — pull + restart only (no Quadlet regeneration)
	taskfile --env $(ENV) run deploy-quick --var TAG=$(TAG)

.PHONY: deploy-service
deploy-service: ## Deploy single service (--var SVC=app)
	taskfile --env $(ENV) run deploy-service --var TAG=$(TAG)

.PHONY: dev
dev: ## Start full local environment
	taskfile --env $(ENV) run dev --var TAG=$(TAG)

.PHONY: dev-down
dev-down: ## Stop local environment
	taskfile --env $(ENV) run dev-down --var TAG=$(TAG)

.PHONY: dev-logs
dev-logs: ## Follow local logs (--var SVC=app for single service)
	taskfile --env $(ENV) run dev-logs --var TAG=$(TAG)

.PHONY: dev-ps
dev-ps: ## Show running local services
	taskfile --env $(ENV) run dev-ps --var TAG=$(TAG)

.PHONY: dev-restart
dev-restart: ## Restart a service locally (--var SVC=app)
	taskfile --env $(ENV) run dev-restart --var TAG=$(TAG)

.PHONY: generate
generate: ## Generate Quadlet files from docker-compose.yml + .env.prod
	taskfile --env $(ENV) run generate --var TAG=$(TAG)

.PHONY: logs
logs: ## View production logs (--var SVC=app)
	taskfile --env $(ENV) run logs --var TAG=$(TAG)

.PHONY: push
push: ## Build and push all images to registry
	taskfile --env $(ENV) run push --var TAG=$(TAG)

.PHONY: ram
ram: ## Check RAM usage on production server
	taskfile --env $(ENV) run ram --var TAG=$(TAG)

.PHONY: release
release: ## Tagged release — build, push, deploy with version tag
	taskfile --env $(ENV) run release --var TAG=$(TAG)

.PHONY: restart
restart: ## Restart production service (--var SVC=app)
	taskfile --env $(ENV) run restart --var TAG=$(TAG)

.PHONY: setup-server
setup-server: ## First-time production server setup
	taskfile --env $(ENV) run setup-server --var TAG=$(TAG)

.PHONY: status
status: ## Show production service status
	taskfile --env $(ENV) run status --var TAG=$(TAG)

.PHONY: stop
stop: ## Stop production service (--var SVC=app)
	taskfile --env $(ENV) run stop --var TAG=$(TAG)

.PHONY: upload-quadlets
upload-quadlets: ## Upload Quadlet files without restarting
	taskfile --env $(ENV) run upload-quadlets --var TAG=$(TAG)

# ─── Pipeline stages ─────────────────
.PHONY: stage-test
stage-test: ## Pipeline stage: test
	taskfile --env $(ENV) run build --var TAG=$(TAG)

.PHONY: stage-build
stage-build: ## Pipeline stage: build
	taskfile --env $(ENV) run push --var TAG=$(TAG)

.PHONY: stage-generate
stage-generate: ## Pipeline stage: generate
	taskfile --env $(ENV) run generate --var TAG=$(TAG)

.PHONY: stage-deploy
stage-deploy: ## Pipeline stage: deploy
	taskfile --env prod run deploy-quick --var TAG=$(TAG)

.PHONY: test
test: ## Validate Taskfile and show tasks
	@echo "═══════════════════════════════════════════════════════════════"
	@echo "  codereview.pl Example (Real-World Production)"
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
	@echo "✅ codereview.pl example test completed"

.PHONY: pipeline
pipeline: stage-test stage-build stage-generate stage-deploy ## Run full pipeline
