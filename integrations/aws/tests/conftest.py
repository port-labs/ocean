import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Callable, Dict, Generator
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError
import port_ocean.context.ocean as port_ocean_ctx
from port_ocean.ocean import Ocean

MOCK_ORG_URL = "https://mock-organization-url.com"
MOCK_PERSONAL_ACCESS_TOKEN = "mock-personal-access_token"


@pytest.fixture
def mock_ocean_app() -> Ocean:
    """Create a mock Ocean app with default configuration."""
    app = MagicMock(spec=Ocean)
    app.config = MagicMock()
    app.config.integration = MagicMock()
    app.config.integration.config = {}
    app.integration_router = MagicMock()
    app.port_client = MagicMock()
    app.cache_provider = AsyncMock(return_value=None)
    return app


@pytest.fixture
def ocean_context(mock_ocean_app: Ocean) -> Callable[[Dict[str, Any]], None]:
    """Initialize PortOcean context with customizable config."""

    def _setup(config: Dict[str, Any] = {}) -> None:
        mock_ocean_app.config.integration.config = config
        try:
            initialize_port_ocean_context(mock_ocean_app)
        except PortOceanContextAlreadyInitializedError:
            pass

    return _setup


@pytest.fixture
def mock_event_context() -> Generator[None, None, None]:
    """Mock the event context."""
    with patch("port_ocean.context.event.event_context", new=MagicMock()):
        yield


@pytest.fixture
def mock_session() -> AsyncMock:
    """Mock AWS session with paginated client."""

    class MockPaginator:
        def __init__(self) -> None:
            self.called = False

        async def paginate(self, TypeName: str) -> AsyncGenerator[Dict[str, Any], None]:
            self.called = True
            yield {"ResourceDescriptions": [{"Identifier": "test-id"}]}

    class MockClient(AsyncMock):
        def get_paginator(self, name: str) -> MockPaginator:
            return MockPaginator()

    @asynccontextmanager
    async def mock_client(
        service_name: str, **kwargs: Any
    ) -> AsyncGenerator[MockClient, None]:
        yield MockClient()

    session = AsyncMock(region_name="us-west-2")
    session.client = session.create_client = mock_client
    return session


@pytest.fixture
def mock_account_id() -> str:
    """Mock AWS account ID."""
    return "123456789012"


@pytest.fixture
def mock_resource_config() -> MagicMock:
    """Mock resource config with region allowance."""
    config = MagicMock()
    config.selector.is_region_allowed.return_value = True
    return config


@pytest.fixture(autouse=True)
def reset_port_ocean_context() -> Generator[None, None, None]:
    """Reset PortOcean context before and after each test."""
    port_ocean_ctx._port_ocean = port_ocean_ctx.PortOceanContext(None)
    yield
    port_ocean_ctx._port_ocean = port_ocean_ctx.PortOceanContext(None)


# Shared mocks for AWS resource tests
class MockSTSClient:
    async def get_caller_identity(self) -> dict[str, str]:
        return {"Account": "123456789012"}

    async def __aenter__(self) -> "MockSTSClient":
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: Any
    ) -> None:
        pass


class MockPaginator:
    async def paginate(self, TypeName: str) -> AsyncGenerator[dict[str, Any], None]:
        yield {"ResourceDescriptions": [{"Identifier": "test-id", "Properties": "{}"}]}


class MockClient:
    async def describe_stacks(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "Stacks": [{"StackName": "test-stack", "Foo": "Bar"}],
            "NextToken": None,
        }

    def get_paginator(self, name: str) -> MockPaginator:
        return MockPaginator()

    async def __aenter__(self) -> "MockClient":
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: Any
    ) -> None:
        pass

    async def list_group_resources(self, Group: str) -> Any:
        return []

    async def list_groups(self) -> Any:
        return []
