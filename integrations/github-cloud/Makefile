.PHONY: install test lint format clean docker-build docker-run

# Python environment
VENV = .venv
PYTHON = $(VENV)/bin/python
PIP = $(VENV)/bin/pip
POETRY = poetry

# Docker
DOCKER_IMAGE = githubcloud
DOCKER_TAG = latest

install:
	$(POETRY) install

test:
	$(POETRY) run pytest

lint:
	$(POETRY) run black --check .
	$(POETRY) run mypy .
	$(POETRY) run pylint .
	$(POETRY) run ruff check .

format:
	$(POETRY) run black .
	$(POETRY) run ruff check --fix .

clean:
	rm -rf $(VENV)
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf __pycache__
	rm -rf .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

docker-build:
	docker build -t $(DOCKER_IMAGE):$(DOCKER_TAG) .

docker-run:
	docker run -p 8000:8000 $(DOCKER_IMAGE):$(DOCKER_TAG)

# Development
dev:
	$(POETRY) run python debug.py

# Release
release:
	$(POETRY) version $(VERSION)
	$(POETRY) build
	$(POETRY) publish

# Documentation
docs:
	$(POETRY) run towncrier build --version $(VERSION)

# Dependencies
update-deps:
	$(POETRY) update

# Type checking
type-check:
	$(POETRY) run mypy .

# Security
security-check:
	$(POETRY) run bandit -r .

# Coverage
coverage:
	$(POETRY) run pytest --cov=. --cov-report=html

# Clean coverage
clean-coverage:
	rm -rf htmlcov
	rm -f .coverage

# All checks
check: lint test type-check security-check

# Help
help:
	@echo "Available commands:"
	@echo "  install        - Install dependencies"
	@echo "  test          - Run tests"
	@echo "  lint          - Run linters"
	@echo "  format        - Format code"
	@echo "  clean         - Clean up"
	@echo "  docker-build  - Build Docker image"
	@echo "  docker-run    - Run Docker container"
	@echo "  dev           - Run in development mode"
	@echo "  release       - Create a new release"
	@echo "  docs          - Build documentation"
	@echo "  update-deps   - Update dependencies"
	@echo "  type-check    - Run type checking"
	@echo "  security-check - Run security checks"
	@echo "  coverage      - Run tests with coverage"
	@echo "  clean-coverage - Clean coverage files"
	@echo "  check         - Run all checks"
	@echo "  help          - Show this help message"
