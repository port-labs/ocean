## Agent instructions

Don't on diagnostics that are unrelated to the task or issue you've been tasked with. Resolve diagnostics only when you're asked to resolve them or when you introduce them.

## Build, Lint, and Test Commands

This project uses `poetry` for dependency management.

- **Install dependencies:** `poetry install`
- **Run linters:** `poetry run ruff check .` and `poetry run black .`
- **Run type checker:** `poetry run mypy .`
- **Run all tests:** `poetry run pytest`
- **Run a single test file:** `poetry run pytest tests/path/to/test_file.py`
- **Run a single test function:** `poetry run pytest tests/path/to/test_file.py::test_function_name`

## Code Style Guidelines

- **Formatting:** Use `black` with a line length of 88 characters.
- **Imports:** Group imports into standard library, third-party, and application-specific. Use `from ... import ...`.
- **Types:** Use type hints extensively.
- **Naming Conventions:**
  - Classes: `PascalCase`
  - Functions/variables: `snake_case`
  - Constants: `UPPER_SNAKE_CASE`
- **Asynchronous Code:** Use `asyncio` and `async/await` for asynchronous operations.
- **Logging:** Use `loguru` for logging.
