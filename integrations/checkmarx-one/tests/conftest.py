import pytest
import asyncio
from unittest.mock import AsyncMock
from aiolimiter import AsyncLimiter
from typing import Any, Dict, List, Generator


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_checkmarx_client() -> AsyncMock:
    """Create a mock CheckmarxClient for testing."""
    mock_client = AsyncMock()

    # Set up common attributes
    mock_client.base_url = "https://ast.checkmarx.net"
    mock_client.iam_url = "https://iam.checkmarx.net"
    mock_client.tenant = "test-tenant"
    mock_client.api_key = "test-api-key"
    mock_client.client_id = None
    mock_client.client_secret = None

    # Set up default return values with proper async mock methods
    mock_client.get_projects = AsyncMock()
    mock_client.get_scans = AsyncMock()
    mock_client.get_project_by_id = AsyncMock(return_value={})
    mock_client.get_scan_by_id = AsyncMock(return_value={})

    return mock_client


@pytest.fixture
def sample_project() -> Dict[str, Any]:
    """Sample project data for testing."""
    return {
        "id": "proj-123",
        "name": "Test Project",
        "description": "A test project for unit testing",
        "status": "active",
        "createdAt": "2024-01-01T00:00:00Z",
        "updatedAt": "2024-01-01T00:00:00Z",
    }


@pytest.fixture
def sample_scan() -> Dict[str, Any]:
    """Sample scan data for testing."""
    return {
        "id": "scan-456",
        "projectId": "proj-123",
        "status": "completed",
        "type": "sast",
        "createdAt": "2024-01-01T00:00:00Z",
        "updatedAt": "2024-01-01T00:00:00Z",
        "results": {"high": 5, "medium": 10, "low": 15},
    }


@pytest.fixture
def sample_projects_batch(sample_project: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Sample batch of projects for testing pagination."""
    return [
        sample_project,
        {
            "id": "proj-456",
            "name": "Another Test Project",
            "description": "Another test project",
            "status": "active",
            "createdAt": "2024-01-02T00:00:00Z",
            "updatedAt": "2024-01-02T00:00:00Z",
        },
        {
            "id": "proj-789",
            "name": "Third Test Project",
            "description": "Third test project",
            "status": "inactive",
            "createdAt": "2024-01-03T00:00:00Z",
            "updatedAt": "2024-01-03T00:00:00Z",
        },
    ]


@pytest.fixture
def sample_scans_batch(sample_scan: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Sample batch of scans for testing pagination."""
    return [
        sample_scan,
        {
            "id": "scan-789",
            "projectId": "proj-123",
            "status": "running",
            "type": "sca",
            "createdAt": "2024-01-02T00:00:00Z",
            "updatedAt": "2024-01-02T00:00:00Z",
            "results": None,
        },
        {
            "id": "scan-101",
            "projectId": "proj-456",
            "status": "failed",
            "type": "sast",
            "createdAt": "2024-01-03T00:00:00Z",
            "updatedAt": "2024-01-03T00:00:00Z",
            "results": None,
        },
    ]


@pytest.fixture
def mock_rate_limiter() -> AsyncLimiter:
    """Create a mock rate limiter for testing."""
    return AsyncLimiter(3600, 3600)


@pytest.fixture
def checkmarx_config() -> Dict[str, str]:
    """Sample Checkmarx configuration for testing."""
    return {
        "checkmarx_base_url": "https://ast.checkmarx.net",
        "checkmarx_iam_url": "https://iam.checkmarx.net",
        "checkmarx_tenant": "test-tenant",
        "checkmarx_api_key": "test-api-key",
    }


@pytest.fixture
def checkmarx_oauth_config() -> Dict[str, str]:
    """Sample Checkmarx OAuth configuration for testing."""
    return {
        "checkmarx_base_url": "https://ast.checkmarx.net",
        "checkmarx_iam_url": "https://iam.checkmarx.net",
        "checkmarx_tenant": "test-tenant",
        "checkmarx_client_id": "test-client-id",
        "checkmarx_client_secret": "test-client-secret",
    }


# Pytest configuration
def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: mark test as a unit test")
    config.addinivalue_line("markers", "integration: mark test as an integration test")
    config.addinivalue_line("markers", "slow: mark test as slow running")


# Async test configuration
@pytest.fixture(autouse=True)
def configure_async_tests() -> None:
    """Configure async test environment."""
    # Set up any async-specific configuration here
    pass
