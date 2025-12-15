# Harbor Integration Tests

This directory contains unit tests for the Harbor integration, following the same patterns used in the Jira integration.

## Test Structure

```
tests/
├── __init__.py                   # Makes tests a Python package
├── conftest.py                   # Shared pytest fixtures
├── test_client.py                # Tests for HarborClient
├── test_initialize_client.py     # Tests for client factory
├── test_processors.py            # Tests for webhook processors
├── test_utils.py                 # Tests for utility functions
└── test_sample.py                # Basic sanity tests
```

## Test Coverage

### 1. Client Tests (`test_client.py`)
- Client initialization (with and without auth)
- API request handling (success, failure, rate limiting)
- Response parsing
- Pagination logic
- Resource-specific methods:
  - `get_projects()`
  - `get_repositories()`
  - `get_artifacts_for_repository()`
  - `get_single_artifact()`
  - `get_users()`

### 2. Utility Tests (`test_utils.py`)
- `parse_resource_url()` - Parse Harbor webhook resource URLs
  - Tag references
  - Digest references
  - Invalid formats
- `split_repository_name()` - Split repository names into project/repo
  - Valid formats
  - Nested paths
  - Invalid formats

### 3. Webhook Processor Tests (`test_processors.py`)
- Event filtering (`should_process_event`)
- Kind matching (`get_matching_kinds`)
- Authentication with webhook secrets
- Payload validation
- Event handling:
  - PUSH_ARTIFACT (with API fetch)
  - DELETE_ARTIFACT
  - Error scenarios (not found, API errors)
  - Invalid resource URLs

### 4. Client Factory Tests (`test_initialize_client.py`)
- Client creation with basic auth
- Client creation without auth
- Default configurations
- Partial credentials handling

### 5. Sample Tests (`test_sample.py`)
- Basic pytest infrastructure verification

## Running Tests

### Run all tests
```bash
cd integrations/harbor
pytest tests/
```

### Run specific test file
```bash
pytest tests/test_client.py
```

### Run specific test
```bash
pytest tests/test_client.py::test_client_initialization
```

### Run with coverage
```bash
pytest tests/ --cov=. --cov-report=html
```

### Run with verbose output
```bash
pytest tests/ -v
```

### Run with output capture disabled (see print statements)
```bash
pytest tests/ -s
```

## Test Patterns

### Fixtures (`conftest.py`)
- `mock_ocean_context`: Mocks the Ocean context (auto-used in all tests)
- `mock_harbor_client`: Creates a HarborClient with auth
- `mock_harbor_client_no_auth`: Creates a HarborClient without auth

### Common Testing Patterns

#### 1. Mocking API Requests
```python
with patch.object(
    mock_harbor_client, "_send_api_request", new_callable=AsyncMock
) as mock_request:
    mock_request.return_value = {"key": "value"}
    result = await mock_harbor_client.get_projects()
```

#### 2. Testing Async Generators
```python
async def mock_generator(*args: Any, **kwargs: Any) -> Any:
    yield [{"id": 1}]

mock_paginated.return_value = mock_generator()
```

#### 3. Testing Exception Handling
```python
mock_request.side_effect = Exception("API Error")
# Verify graceful error handling
```

## Key Dependencies

- `pytest` - Test framework
- `pytest-asyncio` - Async test support
- `httpx` - HTTP client (used by Harbor client)
- `port_ocean` - Ocean framework

## Notes

- All async tests must be decorated with `@pytest.mark.asyncio`
- Fixtures in `conftest.py` are automatically available to all tests
- Mock the `ocean` context to avoid actual API calls
- Use `AsyncMock` for async methods, `MagicMock` for sync methods
- Follow the AAA pattern: Arrange, Act, Assert

## Adding New Tests

When adding new tests:

1. **Test naming**: Use descriptive names starting with `test_`
2. **Fixtures**: Add shared fixtures to `conftest.py`
3. **Mocking**: Mock external dependencies (API calls, ocean context)
4. **Coverage**: Aim for both happy path and error scenarios
5. **Async**: Use `@pytest.mark.asyncio` for async functions
6. **Documentation**: Add docstrings explaining what the test validates

## Test Statistics

- **Total test files**: 5
- **Total test cases**: ~50+
- **Coverage areas**: Client, Utils, Webhooks, Factory
- **Mock patterns**: AsyncMock, MagicMock, patch

## Related Documentation

- [pytest documentation](https://docs.pytest.org/)
- [pytest-asyncio documentation](https://pytest-asyncio.readthedocs.io/)
- [Jira integration tests](../../jira/tests/) - Reference implementation

