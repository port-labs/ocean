.PHONY: install test test-verbose lint format clean

# Install dependencies
install:
	poetry install

# Run tests
test:
	poetry run pytest tests/ -v

# Run tests with coverage
test-coverage:
	poetry run pytest tests/ -v --cov=harbor --cov-report=html --cov-report=term

# Run tests with verbose output
test-verbose:
	poetry run pytest tests/ -v -s

# Run specific test file
test-client:
	poetry run pytest tests/test_harbor_client.py -v

test-exporters:
	poetry run pytest tests/test_exporters.py -v

test-webhooks:
	poetry run pytest tests/test_webhook_processors.py -v

test-integration:
	poetry run pytest tests/test_integration.py -v

# Lint code
lint:
	poetry run flake8 harbor/ tests/
	poetry run mypy harbor/

# Format code
format:
	poetry run black harbor/ tests/
	poetry run isort harbor/ tests/

# Clean up
clean:
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Run integration tests against live Harbor instance
test-integration-live:
	@echo "Starting Harbor integration tests against live instance..."
	@echo "Make sure Harbor is running on localhost:8081"
	poetry run pytest tests/ -v -m "not unit" --harbor-url=http://localhost:8081

# Development setup
dev-setup: install
	poetry run pre-commit install

# Check code quality
quality-check: lint test-coverage
	@echo "Quality check completed successfully!"