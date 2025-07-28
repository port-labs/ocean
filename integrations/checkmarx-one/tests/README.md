# Checkmarx One Integration Test Suite

This directory contains comprehensive unit tests for the Checkmarx One integration.

## Test Structure

The test suite is organized into the following files:

### Core Component Tests
- **`test_client.py`** - Tests for the `CheckmarxClient` class
  - Authentication (API key and OAuth)
  - HTTP request handling and error cases
  - Rate limiting and pagination
  - Token management and refresh

- **`test_exporters.py`** - Tests for project and scan exporters
  - `CheckmarxProjectExporter` functionality
  - `CheckmarxScanExporter` functionality
  - Pagination and resource fetching

- **`test_abstract_exporter.py`** - Tests for the abstract base exporter
  - Abstract base class behavior
  - Interface compliance

### Factory and Initialization Tests
- **`test_client_factory.py`** - Tests for client factory functions
  - `create_checkmarx_client()`
  - `create_project_exporter()`
  - `create_scan_exporter()`

- **`test_initialize_client.py`** - Tests for client initialization
  - Configuration validation
  - Authentication method selection
  - Error handling

### Integration Handler Tests
- **`test_main.py`** - Tests for main integration handlers
  - `on_start()` handler
  - `on_project_resync()` handler
  - `on_scan_resync()` handler

### Utility Tests
- **`test_utils.py`** - Tests for utility functions and enums
  - `ObjectKind` enum behavior

### Configuration and Fixtures
- **`conftest.py`** - Pytest configuration and shared fixtures
- **`test_sample.py`** - Basic integration structure tests

## Running Tests

### Prerequisites
Make sure you have the required dependencies installed:
```bash
cd integrations/checkmarx-one
poetry install
```

### Run All Tests
```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=.

# Run specific test file
pytest tests/test_client.py

# Run specific test class
pytest tests/test_client.py::TestCheckmarxClient

# Run specific test
pytest tests/test_client.py::TestCheckmarxClient::test_client_initialization_with_api_key
```

### Test Markers
The test suite uses custom markers:

- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.slow` - Slow-running tests

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Skip slow tests
pytest -m "not slow"
```

### Async Test Support
The test suite includes full support for async tests with proper event loop management.

## Test Coverage

The test suite provides comprehensive coverage for:

### Authentication & Security
- ✅ API key authentication
- ✅ OAuth client credentials authentication
- ✅ Token refresh and expiration handling
- ✅ Authentication error scenarios

### HTTP Client Functionality
- ✅ API request methods (GET, POST)
- ✅ Error handling (401, 403, 404, 429, 500+)
- ✅ Rate limiting
- ✅ Request retry logic
- ✅ Pagination handling

### Data Export Operations
- ✅ Project listing and fetching
- ✅ Scan listing and fetching
- ✅ Resource filtering and pagination
- ✅ Empty result handling

### Integration Handlers
- ✅ Startup initialization
- ✅ Project resync operations
- ✅ Scan resync operations
- ✅ Error handling in handlers

### Factory and Initialization
- ✅ Client factory functions
- ✅ Configuration validation
- ✅ Authentication method selection
- ✅ Initialization error scenarios

### Utilities and Enums
- ✅ ObjectKind enum behavior
- ✅ Type safety and validation

## Mock Strategy

The tests use a comprehensive mocking strategy:

### HTTP Client Mocking
- Mock `http_async_client` for all HTTP operations
- Simulate various response scenarios (success, errors, rate limits)
- Test retry logic and error handling

### Ocean Context Mocking
- Mock Ocean integration context
- Provide test configuration data
- Isolate tests from external dependencies

### Rate Limiter Mocking
- Mock rate limiting behavior
- Test rate limit enforcement
- Verify proper rate limit handling

## Best Practices

The test suite follows Ocean integration testing best practices:

### 1. Async Test Patterns
```python
@pytest.mark.asyncio
async def test_async_function():
    # Use AsyncMock for async dependencies
    mock_client = AsyncMock()
    result = await function_under_test(mock_client)
    assert result == expected
```

### 2. Error Scenario Testing
```python
def test_error_handling():
    with pytest.raises(SpecificException, match="error message"):
        function_that_should_fail()
```

### 3. Patch Strategy
```python
@patch('module.dependency')
def test_with_mocked_dependency(mock_dep):
    # Arrange, Act, Assert
```

### 4. Fixture Usage
```python
def test_with_fixtures(mock_checkmarx_client, sample_project):
    # Use shared fixtures for common test data
```

## Debugging Tests

### Running Individual Tests
```bash
# Run with debugging output
pytest -s tests/test_client.py::test_specific_test

# Run with pdb on failure
pytest --pdb tests/test_client.py

# Run with verbose logging
pytest -v --log-cli-level=DEBUG
```

### Common Issues
1. **Import Errors** - Ensure you're in the integration directory
2. **Async Errors** - Check event loop configuration in conftest.py
3. **Mock Issues** - Verify mock setup matches the actual interface

## Contributing

When adding new tests:

1. Follow the existing naming conventions
2. Use appropriate fixtures from `conftest.py`
3. Add proper docstrings and comments
4. Test both success and error scenarios
5. Use appropriate async patterns for async code
6. Group related tests in classes
7. Add appropriate test markers

### Example Test Structure
```python
class TestNewFeature:
    @pytest.mark.asyncio
    async def test_success_scenario(self, mock_client):
        """Test successful operation."""
        # Arrange
        mock_client.method.return_value = expected_result

        # Act
        result = await function_under_test(mock_client)

        # Assert
        assert result == expected_result
        mock_client.method.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_scenario(self, mock_client):
        """Test error handling."""
        # Arrange
        mock_client.method.side_effect = Exception("Test error")

        # Act & Assert
        with pytest.raises(Exception, match="Test error"):
            await function_under_test(mock_client)
```

## Integration with CI/CD

The test suite is designed to integrate with continuous integration:

```bash
# Basic CI test command
pytest --cov=. --cov-report=xml --junitxml=test-results.xml

# With specific markers for CI
pytest -m "not slow" --cov=. --cov-report=xml
```

This comprehensive test suite ensures the reliability and maintainability of the Checkmarx One integration.
