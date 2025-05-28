import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from typing import Any, Dict, List, Generator
from snyk.client import SnykClient
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.context.event import EventContext
from aiolimiter import AsyncLimiter
import time
import asyncio

MOCK_API_URL = "https://api.snyk.io/v1"
MOCK_TOKEN = "dummy_token"
MOCK_PROJECT_ID = "12345"
MOCK_ISSUES = [{"id": "issue1"}, {"id": "issue2"}]
MOCK_ORG_URL = "https://your_organization_url.com"
MOCK_PERSONAL_ACCESS_TOKEN = "personal_access_token"


# Port Ocean Mocks
@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Fixture to mock the Ocean context initialization."""
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = {
            "organization_url": MOCK_ORG_URL,
            "personal_access_token": MOCK_PERSONAL_ACCESS_TOKEN,
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        mock_ocean_app.cache_provider = AsyncMock()
        mock_ocean_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.fixture
def mock_event_context() -> Generator[MagicMock, None, None]:
    """Fixture to mock the event context."""
    mock_event = MagicMock(spec=EventContext)
    mock_event.event_type = "test_event"
    mock_event.trigger_type = "manual"
    mock_event.attributes = {}
    mock_event._deadline = 999999999.0
    mock_event._aborted = False

    with patch("port_ocean.context.event.event", mock_event):
        yield mock_event


@pytest.fixture
def snyk_client() -> SnykClient:
    """Fixture to create a SnykClient instance for testing."""
    return SnykClient(
        token=MOCK_TOKEN,
        api_url=MOCK_API_URL,
        app_host=None,
        organization_ids=None,
        group_ids=None,
        webhook_secret=None,
        rate_limiter=AsyncLimiter(5, 1),
    )


@pytest.mark.asyncio
async def test_send_api_request_rate_limit(snyk_client: SnykClient) -> None:
    """Test rate limit enforcement on API request."""
    with patch.object(
        snyk_client.http_client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value.json = AsyncMock(return_value={})
        mock_request.return_value.raise_for_status = AsyncMock()

        async def make_request() -> None:
            await snyk_client._send_api_request(url=f"{MOCK_API_URL}/test")
            await mock_request.return_value.raise_for_status()

        start_time = time.monotonic()

        await asyncio.gather(*[make_request() for _ in range(15)])

        elapsed_time = time.monotonic() - start_time

        assert (
            elapsed_time >= 1.0
        ), "Rate limiter did not properly enforce the rate limit."


@pytest.mark.asyncio
async def test_get_paginated_resources(
    snyk_client: SnykClient, mock_event_context: MagicMock
) -> None:
    """Test getting paginated resources with mocked response."""

    async def mock_send_api_request(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        url = kwargs.get("url")
        if url and url.endswith("/page1"):
            return {"data": [{"id": "item1"}], "links": {"next": "/rest/page2"}}
        elif url and url.endswith("/page2"):
            return {"data": [{"id": "item2"}], "links": {"next": ""}}
        return {}

    with patch.object(
        snyk_client, "_send_api_request", side_effect=mock_send_api_request
    ):
        url_path = "/page1"

        resources: List[Dict[str, Any]] = []
        async for resource_batch in snyk_client._get_paginated_resources(
            url_path=url_path
        ):
            resources.extend(resource_batch)

        assert resources == [{"id": "item1"}, {"id": "item2"}]
