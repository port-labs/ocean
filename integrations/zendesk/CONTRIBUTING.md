# Contributing to the Zendesk Integration

Thank you for your interest in contributing to the Zendesk integration for Port Ocean! This document provides guidelines and information for contributors.

## Development Setup

1. **Prerequisites**
   - Python 3.12+
   - Poetry for dependency management
   - Access to a Zendesk instance for testing

2. **Clone and Setup**
   ```bash
   git clone https://github.com/port-labs/ocean.git
   cd ocean/integrations/zendesk
   make install
   ```

3. **Configuration**
   Create a `.env` file with your test Zendesk credentials:
   ```env
   ZENDESK_SUBDOMAIN=your-test-subdomain
   ZENDESK_EMAIL=your-email@company.com
   ZENDESK_TOKEN=your-api-token
   ```

## Development Workflow

### Running the Integration Locally

```bash
make run
```

### Running Tests

```bash
# Run all tests
make test

# Run tests with coverage
poetry run pytest --cov=. --cov-report=html

# Run specific test file
poetry run pytest tests/test_client.py
```

### Code Quality

```bash
# Run all linting and formatting checks
make lint

# Auto-fix formatting issues
make lint/fix

# Check individual tools
poetry run black --check .
poetry run ruff check .
poetry run mypy .
```

## Architecture

### Core Components

1. **`client.py`**: Zendesk API client with authentication and rate limiting
2. **`overrides.py`**: Configuration models for resource selectors
3. **`main.py`**: Integration entry point and resource synchronization handlers
4. **`webhook_processors/`**: Real-time webhook event processors
5. **`initialize_client.py`**: Client factory using Ocean configuration

### Key Design Decisions

- **Authentication**: Support for both API tokens and OAuth for flexibility
- **Rate Limiting**: Built-in semaphore-based request limiting
- **Error Handling**: Comprehensive error handling with retry logic
- **Filtering**: Resource-specific selectors for fine-grained control
- **Webhooks**: Real-time updates for supported entity types

## Adding New Features

### Adding a New Resource Type

1. **Add to `kinds.py`**:
   ```python
   class Kinds(StrEnum):
       # ... existing kinds
       NEW_RESOURCE = "new_resource"
   ```

2. **Add selector in `overrides.py`**:
   ```python
   class NewResourceSelector(Selector):
       custom_filter: str | None = None

   class NewResourceConfig(ResourceConfig):
       kind: Literal["new_resource"]
       selector: NewResourceSelector
   ```

3. **Add client methods in `client.py`**:
   ```python
   async def get_new_resources(self, params: Optional[dict[str, Any]] = None):
       async for resources in self._get_paginated_data("new_resources.json", params, "new_resources"):
           yield resources
   ```

4. **Add sync handler in `main.py`**:
   ```python
   @ocean.on_resync(Kinds.NEW_RESOURCE)
   async def on_resync_new_resources(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
       # Implementation here
   ```

### Adding Webhook Support

1. **Create webhook processor**:
   ```python
   # webhook_processors/new_resource_webhook_processor.py
   class NewResourceWebhookProcessor(AbstractWebhookProcessor):
       # Implementation here
   ```

2. **Register in `main.py`**:
   ```python
   from webhook_processors.new_resource_webhook_processor import NewResourceWebhookProcessor
   ocean.add_webhook_processor("/webhook", NewResourceWebhookProcessor)
   ```

## Testing Guidelines

### Test Structure

- **`test_client.py`**: Test API client functionality
- **`test_webhook_processors.py`**: Test webhook event processing
- **`conftest.py`**: Shared test fixtures and utilities

### Writing Tests

1. **Use fixtures**: Leverage existing fixtures for sample data
2. **Mock external calls**: Use `AsyncMock` for API calls
3. **Test error cases**: Include tests for API errors and edge cases
4. **Test filters**: Verify selector filtering works correctly

### Example Test

```python
@pytest.mark.asyncio
async def test_get_tickets_with_filters(self, mock_client):
    """Test ticket retrieval with status filter."""
    mock_client.get_tickets.return_value = async_generator([sample_tickets])
    
    # Test implementation
    result = []
    async for batch in mock_client.get_tickets({"status": "open"}):
        result.extend(batch)
    
    assert len(result) > 0
    mock_client.get_tickets.assert_called_once_with({"status": "open"})
```

## Documentation

### Code Documentation

- Use type hints for all function parameters and return values
- Add docstrings to all public methods and classes
- Document complex logic and business rules

### README Updates

When adding new features:
1. Update the features list
2. Add configuration examples
3. Update the supported entities table
4. Add troubleshooting information if needed

## Submitting Changes

### Pull Request Process

1. **Create feature branch**: `git checkout -b feature/description`
2. **Make changes**: Follow the coding standards
3. **Add tests**: Ensure new code has test coverage
4. **Update docs**: Update README and docstrings
5. **Run tests**: Ensure all tests pass locally
6. **Submit PR**: Include clear description of changes

### Pull Request Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Tests added/updated
- [ ] Manual testing performed
- [ ] All tests passing

## Documentation
- [ ] README updated if needed
- [ ] Docstrings added/updated
- [ ] CHANGELOG entry added
```

## Code Standards

### Python Style

- Follow PEP 8 style guidelines
- Use type hints consistently
- Maximum line length: 88 characters (Black default)
- Use meaningful variable and function names

### Imports

```python
# Standard library
import asyncio
from typing import Any, Optional

# Third-party
import httpx
from loguru import logger

# Local imports
from zendesk.client import ZendeskClient
from kinds import Kinds
```

### Error Handling

```python
try:
    result = await client.api_call()
except httpx.HTTPStatusError as e:
    logger.error(f"API error {e.response.status_code}: {e}")
    raise
except httpx.RequestError as e:
    logger.error(f"Network error: {e}")
    raise
```

## Common Patterns

### Async Generators

```python
async def get_paginated_data(self) -> AsyncGenerator[list[dict], None]:
    """Get paginated data from API."""
    page = 1
    while True:
        data = await self._fetch_page(page)
        if not data:
            break
        yield data
        page += 1
```

### Configuration Access

```python
from port_ocean.context.ocean import ocean

config = ocean.integration_config
subdomain = config["zendesk_subdomain"]
```

### Logging

```python
from loguru import logger

logger.info("Processing tickets batch")
logger.warning("Rate limit approaching")
logger.error(f"Failed to process ticket {ticket_id}: {error}")
```

## Questions and Support

- **GitHub Issues**: For bug reports and feature requests
- **Discussions**: For questions and general discussion
- **Port Community**: Join the Port community for broader questions

Thank you for contributing to the Zendesk integration!