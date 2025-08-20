import pytest
import asyncio
import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from aiolimiter import AsyncLimiter
from typing import Any, Dict, List, Generator, Callable

# Provide lightweight stubs for port_ocean imports used by the integration
if "port_ocean" not in sys.modules:
    sys.modules["port_ocean"] = types.ModuleType("port_ocean")
    # Mark as a package so submodules can be imported
    setattr(sys.modules["port_ocean"], "__path__", [])

# Create minimal stubs for core and ocean_types used by tests
core_stub: Any = types.ModuleType("port_ocean.core")
sys.modules["port_ocean.core"] = core_stub

ocean_types_stub: Any = types.ModuleType("port_ocean.core.ocean_types")
try:
    from typing import Any as _Any, AsyncIterator as _AsyncIterator

    ocean_types_stub.RAW_ITEM = dict[str, _Any]
    ocean_types_stub.RAW_RESULT = list[dict[str, _Any]]
    ocean_types_stub.ASYNC_GENERATOR_RESYNC_TYPE = _AsyncIterator[
        ocean_types_stub.RAW_RESULT
    ]
except Exception:
    # Fallbacks if typing features are unavailable
    ocean_types_stub.RAW_ITEM = dict
    ocean_types_stub.RAW_RESULT = list
    ocean_types_stub.ASYNC_GENERATOR_RESYNC_TYPE = object
sys.modules["port_ocean.core.ocean_types"] = ocean_types_stub

utils_stub: Any = types.ModuleType("port_ocean.utils")


class _StubHttpAsyncClient:
    async def request(self, *args: Any, **kwargs: Any) -> MagicMock:
        resp = MagicMock()
        resp.json.return_value = {}
        resp.raise_for_status.return_value = None
        return resp

    async def post(self, *args: Any, **kwargs: Any) -> MagicMock:
        return await self.request(*args, **kwargs)


utils_stub.http_async_client = _StubHttpAsyncClient()

# Create cache stub
cache_stub: Any = types.ModuleType("port_ocean.utils.cache")
sys.modules["port_ocean.utils.cache"] = cache_stub


def cache_iterator_result() -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        return func

    return decorator


cache_stub.cache_iterator_result = cache_iterator_result

sys.modules["port_ocean.utils"] = utils_stub

errors_stub: Any = types.ModuleType("port_ocean.cache.errors")


class FailedToReadCacheError(Exception):
    pass


class FailedToWriteCacheError(Exception):
    pass


errors_stub.FailedToReadCacheError = FailedToReadCacheError
errors_stub.FailedToWriteCacheError = FailedToWriteCacheError
sys.modules["port_ocean.cache.errors"] = errors_stub

ocean_stub: Any = types.ModuleType("port_ocean.context.ocean")
ocean_stub.ocean = SimpleNamespace(
    app=SimpleNamespace(
        cache_provider=SimpleNamespace(
            get=AsyncMock(return_value=None), set=AsyncMock()
        )
    )
)
sys.modules["port_ocean.context.ocean"] = ocean_stub

# Create webhook stubs
handlers_stub: Any = types.ModuleType("port_ocean.core.handlers")
sys.modules["port_ocean.core.handlers"] = handlers_stub

webhook_stub: Any = types.ModuleType("port_ocean.core.handlers.webhook")
sys.modules["port_ocean.core.handlers.webhook"] = webhook_stub


# Create WebhookEvent class stub
class WebhookEvent:
    def __init__(
        self,
        payload: Dict[str, Any],
        headers: Dict[str, Any],
        _original_request: Any = None,
    ) -> None:
        self.payload = payload
        self.headers = headers
        self._original_request = _original_request


class EventPayload:
    pass


class EventHeaders:
    pass


class WebhookEventRawResults:
    def __init__(
        self,
        updated_raw_results: List[Dict[str, Any]],
        deleted_raw_results: List[Dict[str, Any]],
    ) -> None:
        self.updated_raw_results = updated_raw_results
        self.deleted_raw_results = deleted_raw_results


webhook_stub.WebhookEvent = WebhookEvent
webhook_stub.EventPayload = EventPayload
webhook_stub.EventHeaders = EventHeaders
webhook_stub.WebhookEventRawResults = WebhookEventRawResults

# Create webhook_event module stub
webhook_event_stub: Any = types.ModuleType(
    "port_ocean.core.handlers.webhook.webhook_event"
)
sys.modules["port_ocean.core.handlers.webhook.webhook_event"] = webhook_event_stub
webhook_event_stub.WebhookEvent = WebhookEvent
webhook_event_stub.EventPayload = EventPayload
webhook_event_stub.EventHeaders = EventHeaders
webhook_event_stub.WebhookEventRawResults = WebhookEventRawResults

# Create port_app_config stubs
port_app_config_stub: Any = types.ModuleType("port_ocean.core.handlers.port_app_config")
sys.modules["port_ocean.core.handlers.port_app_config"] = port_app_config_stub

models_stub: Any = types.ModuleType("port_ocean.core.handlers.port_app_config.models")
sys.modules["port_ocean.core.handlers.port_app_config.models"] = models_stub


class ResourceConfig:
    def __init__(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


models_stub.ResourceConfig = ResourceConfig

# Create abstract webhook processor stub
abstract_webhook_processor_stub: Any = types.ModuleType(
    "port_ocean.core.handlers.webhook.abstract_webhook_processor"
)
sys.modules["port_ocean.core.handlers.webhook.abstract_webhook_processor"] = (
    abstract_webhook_processor_stub
)


class AbstractWebhookProcessor:
    async def authenticate(
        self, payload: Dict[str, Any], headers: Dict[str, Any]
    ) -> bool:
        return True

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return True

    async def validate_payload(self, payload: Dict[str, Any]) -> bool:
        return True

    async def get_matching_kinds(self, event: WebhookEvent) -> List[str]:
        return []

    async def handle_event(
        self, payload: Dict[str, Any], resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        return WebhookEventRawResults([], [])


abstract_webhook_processor_stub.AbstractWebhookProcessor = AbstractWebhookProcessor


# Lightweight replacement for initialize_port_ocean_context used in tests
def initialize_port_ocean_context(app: Any) -> None:
    ocean_stub.ocean = SimpleNamespace(app=app)


class PortOceanContextAlreadyInitializedError(Exception):
    pass


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


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Mock the PortOcean context to prevent initialization errors."""
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = {
            "checkmarx_base_url": "https://ast.checkmarx.net",
            "checkmarx_iam_url": "https://iam.checkmarx.net",
            "checkmarx_tenant": "test-tenant",
            "checkmarx_api_key": "test-api-key",
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        mock_ocean_app.cache_provider = AsyncMock()
        mock_ocean_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


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
