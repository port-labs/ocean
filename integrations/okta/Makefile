# Integration information
INTEGRATION_NAME := okta
INTEGRATION_PATH := integrations/okta

# Include common Makefile
include ../Makefile.common

# Default goal
.DEFAULT_GOAL := install

# Install dependencies
install:
	@echo "Installing Okta integration dependencies..."
	poetry install

# Run tests
test:
	@echo "Running Okta integration tests..."
	poetry run pytest $(INTEGRATION_PATH)/tests/ -v

# Run linting
lint:
	@echo "Running linters for Okta integration..."
	poetry run black --check $(INTEGRATION_PATH)/
	poetry run ruff $(INTEGRATION_PATH)/
	poetry run mypy $(INTEGRATION_PATH)/

# Format code
format:
	@echo "Formatting Okta integration code..."
	poetry run black $(INTEGRATION_PATH)/
	poetry run ruff --fix $(INTEGRATION_PATH)/

# Run integration locally for development
run:
	@echo "Running Okta integration locally..."
	poetry run ocean sail $(INTEGRATION_PATH)/

# Build docker image
build:
	@echo "Building Okta integration docker image..."
	docker build -t port-ocean-$(INTEGRATION_NAME):latest .

# Clean up
clean:
	@echo "Cleaning up Okta integration..."
	find $(INTEGRATION_PATH) -name "*.pyc" -delete
	find $(INTEGRATION_PATH) -name "__pycache__" -type d -exec rm -rf {} +
	rm -rf $(INTEGRATION_PATH)/.pytest_cache

# Run full CI pipeline
ci: install lint test

# Development helpers
dev-install: install
	@echo "Installing development dependencies..."
	poetry install --with dev

# Generate changelog entry
changelog:
	@echo "Generating changelog entry..."
	poetry run towncrier create --content "Added new feature"

.PHONY: install test lint format run build clean ci dev-install changelog