# Generic HTTP Integration Makefile

define check_integration_env
	@if [ -z "$(INTEGRATION_PATH)" ]; then \
		echo "INTEGRATION_PATH is not set. Please set it to the path of the integration."; \
		exit 1; \
	fi
endef

# Default values
INTEGRATION_PATH := integrations/generic-http
VERSION := $(shell grep version pyproject.toml | head -1 | cut -d '"' -f 2)

# Install dependencies
install:
	poetry install

# Run linting
lint:
	poetry run ruff check .
	poetry run black --check .
	poetry run mypy .

# Format code
format:
	poetry run ruff check --fix .
	poetry run black .

# Run tests
test:
	poetry run pytest

# Run integration locally
run:
	poetry run python debug.py

# Build package
build:
	poetry build

# Clean build artifacts
clean:
	rm -rf dist/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete

# Bump version
bump-patch:
	poetry version patch

bump-minor:
	poetry version minor

bump-major:
	poetry version major

# Show current version
version:
	@echo $(VERSION)

.PHONY: install lint format test run build clean bump-patch bump-minor bump-major version






