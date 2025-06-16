---
title: Managing Dependencies
sidebar_label: ⚙️ Managing Dependencies
sidebar_position: 1
---

# ⚙️ Managing Dependencies

When building an Ocean integration, you'll need to manage various dependencies for your project. Ocean framework integrations use Poetry for dependency management, which helps maintain consistent and reproducible builds.

## The `pyproject.toml` File

The `pyproject.toml` file is the central configuration file for your integration. It serves several important purposes:

1. **Version Management**
   - Maintains the integration's current version via the `version` field
   - Should be bumped when releasing a new version
   - Follows semantic versioning (MAJOR.MINOR.PATCH)
   - For beta releases, append `-beta` to the version number

2. **Dependency Management**
   - Lists all required dependencies for the integration
   - Specifies version constraints for each dependency
   - Separates development dependencies from runtime dependencies

3. **Code Quality Tools**
   - Configures automated tools for consistent code quality:
     - `mypy` for type checking
     - `ruff` for linting
     - `black` for code formatting
   - Sets up `towncrier` for maintaining the CHANGELOG
   - Enforces coding standards across the project

Here's an example of a `pyproject.toml` file:

```toml
[tool.poetry]
name = "jira"
version = "0.1.0-beta"
description = "Integration to bring information from Jira into Port"
authors = ["Name Surname <name@domain.com>"]

[tool.poetry.dependencies]
python = "^3.12"
port_ocean = {version = "^0.24.8", extras = ["cli"]}

[tool.poetry.group.dev.dependencies]
# uncomment this if you want to debug the ocean core together with your integration
# port_ocean = { path = '../../', develop = true, extras = ['all'] }
black = "^24.4.2"
mypy = "^1.3.0"
pylint = ">=2.17.4,<4.0.0"
pytest = ">=8.2,<9.0"
pytest-asyncio = ">=0.24.0"
pytest-httpx = ">=0.30.0"
pytest-xdist = "^3.6.1"
ruff = "^0.6.3"
towncrier = "^23.6.0"
cryptography = "^44.0.1"

[tool.towncrier]
directory = "changelog"
filename = "CHANGELOG.md"
title_format = "## {version} ({project_date})"
underlines = [""]

  [[tool.towncrier.type]]
  directory = "breaking"
  name = "Breaking Changes"
  showcontent = true

  [[tool.towncrier.type]]
  directory = "deprecation"
  name = "Deprecations"
  showcontent = true

  [[tool.towncrier.type]]
  directory = "feature"
  name = "Features"
  showcontent = true

  [[tool.towncrier.type]]
  directory = "improvement"
  name = "Improvements"
  showcontent = true

  [[tool.towncrier.type]]
  directory = "bugfix"
  name = "Bug Fixes"
  showcontent = true

  [[tool.towncrier.type]]
  directory = "doc"
  name = "Improved Documentation"
  showcontent = true

[build-system]
requires = ["poetry-core>=1.0.0"]
build-backend = "poetry.core.masonry.api"

[tool.mypy]
exclude = [
    'venv',
    '.venv',
]
plugins = [
    "pydantic.mypy"
]

follow_imports = "silent"
warn_redundant_casts = true
warn_unused_ignores = true
disallow_any_generics = true
check_untyped_defs = true
no_implicit_reexport = true

# for strict mypy: (this is the tricky one :-))
disallow_untyped_defs = true


[tool.ruff]
# Never enforce `E501` (line length violations).
ignore = ["E501"]

[tool.pydantic-mypy]
init_forbid_extra = true
init_typed = true
warn_required_dynamic_aliases = true
warn_untyped_fields = true

[tool.black]
line-length = 88
target-version = ['py311']
include = '\.pyi?$'
exclude = '''
/(
  \scripts
  \.toml
  |\.sh
  |\.git
  |\.ini
  |Dockerfile
  |\.venv
)/
'''

[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
addopts = "-vv -n auto ./tests"

```

## Managing Dependencies with Poetry

Poetry provides a robust CLI for managing dependencies. Here are the most common commands you'll use:

### Installing Dependencies

```bash
# Install all dependencies listed in pyproject.toml
poetry install

# Install dependencies in development mode
poetry install --with dev
```

### Adding Dependencies

```bash
# Add a runtime dependency
poetry add pydantic

# Add a development dependency
poetry add -D pytest

# Add a dependency with a specific version
poetry add pydantic@^2.0.0
```

### Removing Dependencies

```bash
# Remove a runtime dependency
poetry remove pydantic

```

### Updating Dependencies

```bash
# Update all dependencies to their latest versions
poetry update

# Update a specific dependency
poetry update pydantic
```

## Best Practices

1. **Version Constraints**
   - Use caret (`^`) for flexible version ranges
   - Specify minimum versions for security
   - Avoid pinning to exact versions unless necessary

2. **Development Dependencies**
   - Keep development tools in the `dev` group
   - Include testing frameworks as dev dependencies
   - Add code quality tools as dev dependencies

3. **Dependency Organization**
   - Group related dependencies together
   - Document why each dependency is needed
   - Keep the dependency list minimal

4. **Security**
   - Regularly update dependencies
   - Check for known vulnerabilities
   - Use `poetry audit` to scan for issues




:::info Version Management
When releasing a new version of your integration:

1. Update the version in `pyproject.toml`
2. Create a changelog entry using `towncrier`
3. Commit the changes
4. Create a new release tag
:::

For more details on Poetry and dependency management, see the [Poetry documentation](https://python-poetry.org/docs/).
