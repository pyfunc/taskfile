IMAGE = ghcr.io/myorg/myapp
TAG = latest
PYTHON = python3

.PHONY: lint test build deploy clean

lint:
	$(PYTHON) -m ruff check src/
	$(PYTHON) -m ruff format --check src/

test: lint
	$(PYTHON) -m pytest tests/ -v --cov

build: test
	docker build -t $(IMAGE):$(TAG) .

push: build
	docker push $(IMAGE):$(TAG)

deploy: push
	ssh deploy@staging.example.com "docker pull $(IMAGE):$(TAG)"
	ssh deploy@staging.example.com "systemctl restart myapp"

clean:
	rm -rf dist/ build/ *.egg-info
	find . -name __pycache__ -exec rm -rf {} +
