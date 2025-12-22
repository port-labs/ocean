---
title: Testing Standards
sidebar_label: 🧪 Testing Standards
sidebar_position: 3
---

# 🧪 Testing Standards

This guide covers our testing requirements, best practices, and standards for writing tests in Ocean.

## Overview

Ocean uses **pytest** for testing with async support. All contributions must include appropriate tests.

## Running Tests

### Run All Tests

```bash
make test
```

This runs all non-smoke tests with:
- Verbose output (`-vv`)
- Parallel execution (`-n auto`)
- Shows slowest 10 tests (`--durations=10`)
- Color output

### Run Smoke Tests

```bash
make smoke/test
```

Smoke tests are integration tests that verify end-to-end functionality.

### Watch Mode (Development)

```bash
make test/watch
```

Runs tests in watch mode, re-running on file changes.

### Run Specific Tests

```bash
# Run tests in a specific file
pytest path/to/test_file.py

# Run a specific test
pytest path/to/test_file.py::test_function_name

# Run tests matching a pattern
pytest -k "test_pattern"
```

## Test Configuration

**Configuration**: `pyproject.toml`

- **Async mode**: `auto` (automatically detects async tests)
- **Fixture loop scope**: `function` (new event loop per test)
- **Parallel execution**: Enabled (`-n auto`)
- **Markers**: `smoke` for smoke tests

## Test Structure

### Basic Test Example

```python
import pytest
from port_ocean.utils.async_iterators import stream_async_iterators_tasks


async def test_fetch_resources():
    """Test fetching resources from API."""
    client = MyClient()
    resources = []

    async for batch in client.get_paginated_resources("project"):
        resources.extend(batch)

    assert len(resources) > 0
    assert all("id" in r for r in resources)
```

### Async Test Example

```python
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_async_operation():
    """Test async operation with mocking."""
    with patch("module.AsyncClient") as mock_client:
        mock_client.return_value.fetch = AsyncMock(return_value={"data": "test"})

        result = await fetch_data()

        assert result == {"data": "test"}
        mock_client.return_value.fetch.assert_called_once()
```

### Testing Resync Functions

```python
import pytest
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


async def test_resync_function():
    """Test resync function returns correct data."""
    async def resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
        yield [{"id": "1", "name": "Project 1"}]
        yield [{"id": "2", "name": "Project 2"}]

    results = []
    async for batch in resync_projects("project"):
        results.extend(batch)

    assert len(results) == 2
    assert results[0]["id"] == "1"
```

### Testing Webhook Processors

```python
import pytest
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent


async def test_webhook_processor():
    """Test webhook processor handles events correctly."""
    processor = MyWebhookProcessor(
        WebhookEvent(
            payload={"event": "created", "resource": {"id": "1"}},
            headers={}
        )
    )

    assert await processor.should_process_event(processor.event) is True
    assert await processor.get_matching_kinds(processor.event) == ["resource"]

    result = await processor.handle_event(
        processor.event.payload,
        resource_config
    )

    assert len(result.updated_raw_results) > 0
```

## Test Requirements

### Core Framework Tests

For changes to Ocean core, ensure:

- [ ] Unit tests cover new functionality
- [ ] Integration tests verify end-to-end behavior
- [ ] Edge cases are tested
- [ ] Error cases are handled

### Integration Tests

For new or updated integrations, ensure:

- [ ] Integration creates all default resources from scratch
- [ ] Completed a full resync from a freshly installed integration
- [ ] Resync creates entities correctly
- [ ] Resync updates entities correctly
- [ ] Resync detects and deletes entities correctly
- [ ] Resync finishes successfully
- [ ] If new resource kind added, include example data in `examples` folder
- [ ] If resource kind updated, validate with example data
- [ ] Live events work for new/updated resource kinds

### Preflight Checklist

Before submitting PR:

- [ ] Handled rate limiting
- [ ] Handled pagination
- [ ] Implemented code in async
- [ ] Support multi-account (if applicable)

## Test Best Practices

### 1. Use Descriptive Test Names

```python
# ✅ Good
async def test_resync_creates_entities_when_none_exist():
    pass

# ❌ Bad
async def test_resync():
    pass
```

### 2. Test One Thing Per Test

```python
# ✅ Good
async def test_fetch_projects():
    """Test fetching projects."""
    pass

async def test_fetch_issues():
    """Test fetching issues."""
    pass

# ❌ Bad
async def test_fetch_everything():
    """Test fetching projects and issues."""
    pass
```

### 3. Use Fixtures for Common Setup

```python
import pytest


@pytest.fixture
async def mock_client():
    """Create a mock client for testing."""
    client = AsyncMock()
    client.fetch.return_value = {"data": []}
    return client


async def test_with_fixture(mock_client):
    """Test using fixture."""
    result = await mock_client.fetch()
    assert result == {"data": []}
```

### 4. Mock External Dependencies

```python
from unittest.mock import AsyncMock, patch


async def test_with_mock():
    """Test with mocked external dependency."""
    with patch("module.external_api_call") as mock_api:
        mock_api.return_value = {"result": "success"}

        result = await my_function()

        assert result == {"result": "success"}
        mock_api.assert_called_once()
```

### 5. Test Error Cases

```python
import pytest


async def test_handles_api_error():
    """Test error handling."""
    with patch("module.api_call") as mock_api:
        mock_api.side_effect = httpx.HTTPStatusError("Error", request=None, response=None)

        with pytest.raises(MyCustomError):
            await my_function()
```

### 6. Use Parametrize for Multiple Cases

```python
import pytest


@pytest.mark.parametrize("kind,expected_count", [
    ("project", 10),
    ("issue", 50),
    ("user", 5),
])
async def test_fetch_resources(kind, expected_count):
    """Test fetching different resource kinds."""
    resources = await fetch_resources(kind)
    assert len(resources) == expected_count
```

## Testing Async Code

### Async Generators

```python
async def test_async_generator():
    """Test async generator function."""
    async def my_generator():
        yield [1, 2, 3]
        yield [4, 5, 6]

    results = []
    async for batch in my_generator():
        results.extend(batch)

    assert results == [1, 2, 3, 4, 5, 6]
```

### Concurrent Operations

```python
import asyncio


async def test_concurrent_operations():
    """Test concurrent async operations."""
    tasks = [
        fetch_resource("1"),
        fetch_resource("2"),
        fetch_resource("3"),
    ]

    results = await asyncio.gather(*tasks)

    assert len(results) == 3
    assert all(r is not None for r in results)
```

## Smoke Tests

Smoke tests verify end-to-end integration functionality:

```python
import pytest


@pytest.mark.smoke
async def test_full_resync_smoke():
    """Smoke test: Full resync completes successfully."""
    # This test runs against actual Port instance
    # Uses SMOKE_TEST_SUFFIX environment variable
    pass
```

**Running smoke tests**:
```bash
SMOKE_TEST_SUFFIX=my_test make smoke/test
```

## Test Coverage

While not strictly enforced, aim for:

- **Unit tests**: High coverage (>80%) for core logic
- **Integration tests**: Cover main workflows
- **Edge cases**: Test error conditions and boundaries

## CI/CD Testing

All tests must pass in CI before PR merge:

1. **Unit tests**: Run on all PRs
2. **Integration tests**: Run on all PRs
3. **Smoke tests**: May run on specific conditions

## Common Testing Patterns

### Testing Pagination

```python
async def test_pagination():
    """Test paginated data fetching."""
    all_items = []
    async for batch in client.get_paginated_resources():
        all_items.extend(batch)
        if len(all_items) >= 100:  # Limit for test
            break

    assert len(all_items) > 0
```

### Testing Rate Limiting

```python
async def test_rate_limiting():
    """Test rate limiting behavior."""
    with patch("time.sleep") as mock_sleep:
        # Simulate rate limit response
        with patch("module.api_call") as mock_api:
            mock_api.side_effect = [
                httpx.HTTPStatusError("429", request=None, response=Mock(status_code=429)),
                {"data": "success"}
            ]

            result = await fetch_with_retry()

            assert result == {"data": "success"}
            mock_sleep.assert_called()  # Verify retry delay
```

### Testing Error Recovery

```python
async def test_error_recovery():
    """Test recovery from errors."""
    attempts = []

    async def fetch_with_retry():
        for i in range(3):
            try:
                attempts.append(i)
                return await api_call()
            except Exception:
                if i == 2:
                    raise
                await asyncio.sleep(0.1)

    with patch("module.api_call") as mock_api:
        mock_api.side_effect = [Exception(), Exception(), {"success": True}]

        result = await fetch_with_retry()

        assert result == {"success": True}
        assert len(attempts) == 3
```

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Pytest Async Documentation](https://pytest-asyncio.readthedocs.io/)
- [Python Testing Best Practices](https://docs.python-guide.org/writing/tests/)
