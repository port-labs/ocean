---
title: Code Style & Formatting
sidebar_label: 📝 Code Style & Formatting
sidebar_position: 2
---

# 📝 Code Style & Formatting

This guide covers our code style standards, formatting tools, and quality checks.

## Overview

Ocean uses a combination of tools to ensure consistent code style and quality:

- **Black** - Code formatting
- **Ruff** - Fast Python linter
- **MyPy** - Static type checking
- **YAMLlint** - YAML file validation
- **Poetry** - Dependency validation

## Running Linting Checks

### Check Code Quality

Run all linting checks:

```bash
make lint
```

This runs:
- `poetry check` - Validates `pyproject.toml`
- `mypy` - Type checking
- `ruff check` - Code quality checks
- `black --check` - Formatting validation
- `yamllint` - YAML validation

### Auto-fix Issues

Automatically fix formatting and some linting issues:

```bash
make lint/fix
```

This runs:
- `black .` - Formats Python code
- `ruff check --fix .` - Auto-fixes fixable linting issues

:::tip Pre-commit Hooks
Pre-commit hooks automatically run `make lint/fix` on staged files. Install them with:
```bash
make install
```
:::

## Tool Configuration

### Black (Code Formatter)

**Configuration**: `pyproject.toml`

- **Line length**: 88 characters
- **Target version**: Python 3.12
- **Excludes**: `scripts`, `.toml`, `.sh`, `.git`, `.ini`, `Dockerfile`, `.venv`, `integrations`, `docs`, `node_modules`

**Usage**:
```bash
black .                    # Format all files
black --check .            # Check formatting only
black path/to/file.py      # Format specific file
```

### Ruff (Linter)

**Configuration**: `pyproject.toml`

- **Target version**: Python 3.11
- **Ignores**: `E501` (line length - handled by Black)
- **Excludes**: `venv`, `.venv`, `integrations`

**Usage**:
```bash
ruff check .               # Check for issues
ruff check --fix .         # Auto-fix issues
ruff check path/to/file.py # Check specific file
```

### MyPy (Type Checker)

**Configuration**: `pyproject.toml`

- **Mode**: Strict (`disallow_untyped_defs = true`)
- **Plugins**: `pydantic.mypy`
- **Excludes**: `port_ocean/cli/cookiecutter`, `venv`, `.venv`, `integrations`, `docs`, `node_modules`

**Key Settings**:
- `warn_redundant_casts = true`
- `warn_unused_ignores = true`
- `disallow_any_generics = true`
- `check_untyped_defs = true`
- `no_implicit_reexport = true`

**Usage**:
```bash
mypy .                     # Type check all files
mypy path/to/file.py      # Type check specific file
```

### YAMLlint

Validates YAML files for syntax and style issues.

**Usage**:
```bash
yamllint .                 # Check all YAML files
yamllint path/to/file.yml # Check specific file
```

## Code Style Guidelines

### Type Hints

Always use type hints for function parameters and return types:

```python
# ✅ Good
async def fetch_resources(kind: str) -> list[dict[str, Any]]:
    return []

# ❌ Bad
async def fetch_resources(kind):
    return []
```

### Import Organization

Imports should be organized as:
1. Standard library imports
2. Third-party imports
3. Local application imports

```python
# ✅ Good
import asyncio
from typing import Any, Dict, List

import httpx
from loguru import logger

from port_ocean.context.ocean import ocean
from integration.client import MyClient
```

### Naming Conventions

- **Variables/Functions**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private**: Prefix with `_`

```python
# ✅ Good
MAX_RETRIES = 3
client = MyClient()

class ResourceExporter:
    def _internal_method(self):
        pass

# ❌ Bad
maxRetries = 3
Client = MyClient()
```

### Line Length

- Maximum line length: **88 characters** (Black default)
- Break long lines appropriately
- Use parentheses for implicit line continuation

```python
# ✅ Good
result = (
    await client.fetch_data(
        endpoint="/api/resources",
        params={"kind": kind, "limit": 100}
    )
)

# ❌ Bad (too long)
result = await client.fetch_data(endpoint="/api/resources", params={"kind": kind, "limit": 100})
```

### Async/Await

Always use async/await for I/O operations:

```python
# ✅ Good
async def fetch_data(url: str) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()

# ❌ Bad
def fetch_data(url: str) -> dict[str, Any]:
    response = requests.get(url)
    return response.json()
```

### Error Handling

Use specific exception types and provide meaningful error messages:

```python
# ✅ Good
async def fetch_resource(resource_id: str) -> dict[str, Any]:
    try:
        return await client.get(f"/resources/{resource_id}")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise ResourceNotFoundError(f"Resource {resource_id} not found") from e
        raise

# ❌ Bad
async def fetch_resource(resource_id: str) -> dict[str, Any]:
    return await client.get(f"/resources/{resource_id}")  # No error handling
```

## Pre-commit Hooks

Pre-commit hooks automatically run checks before commits. They're installed with `make install`.

**Hooks configured**:
- `trailing-whitespace` - Removes trailing whitespace
- `end-of-file-fixer` - Ensures files end with newline
- `check-yaml` - Validates YAML syntax
- `check-added-large-files` - Prevents large file commits
- `check-merge-conflict` - Detects merge conflict markers
- `check-executables-have-shebangs` - Validates shebangs
- `check-symlinks` - Validates symlinks
- `detect-aws-credentials` - Detects AWS credentials
- `fix lint` - Runs `make lint/fix` on Python files

## CI/CD Checks

All PRs must pass CI checks:

1. **Linting**: `make lint` (black, ruff, mypy, yamllint)
2. **Tests**: Unit and integration tests
3. **PR Title**: Must match `[Type] Description` format

## Common Issues and Fixes

### Black Formatting Issues

```bash
# Fix automatically
make lint/fix
# or
black .
```

### MyPy Type Errors

```python
# Add type hints
def my_function(param: str) -> int:
    return len(param)

# Use type: ignore for unavoidable issues (use sparingly)
result = some_untyped_function()  # type: ignore
```

### Ruff Warnings

```bash
# See what's wrong
ruff check .

# Auto-fix what's possible
ruff check --fix .
```

## IDE Configuration

### VS Code

Add to `.vscode/settings.json`:

```json
{
  "python.formatting.provider": "black",
  "python.linting.enabled": true,
  "python.linting.ruffEnabled": true,
  "python.linting.mypyEnabled": true,
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": true
  }
}
```

### PyCharm

1. Install Black plugin
2. Configure Black as external tool
3. Enable "Reformat code" on save

## Best Practices

1. **Run linting before committing**: `make lint`
2. **Fix issues automatically**: `make lint/fix`
3. **Use type hints**: Helps catch errors early
4. **Keep functions small**: Single responsibility principle
5. **Write clear variable names**: Self-documenting code
6. **Follow PEP 8**: Python style guide (with Black modifications)

## Resources

- [Black Documentation](https://black.readthedocs.io/)
- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [MyPy Documentation](https://mypy.readthedocs.io/)
- [PEP 8 Style Guide](https://peps.python.org/pep-0008/)
