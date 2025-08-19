# Makefile for Zendesk Ocean Integration

# Install dependencies
install:
	poetry install

# Run the integration locally in debug mode
run:
	poetry run python debug.py

# Run tests
test:
	poetry run pytest

# Format code
format:
	poetry run black .
	poetry run isort .

# Lint code
lint:
	poetry run ruff check .
	poetry run mypy .

# Clean up
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

.PHONY: install run test format lint clean