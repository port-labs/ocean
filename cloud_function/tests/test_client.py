from typing import Any, AsyncGenerator
import pytest
import httpx
from aiohttp import web

from client import CloudFunctionClient


class MockFunctionServer:
    """A simple HTTP server that simulates a cloud function endpoint."""

    def __init__(self) -> None:
        self.responses: list[dict[str, Any]] = []
        self.received_requests: list[dict[str, Any]] = []
        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self.port: int = 0

    async def handle_request(self, request: web.Request) -> web.Response:
        body = await request.json()
        self.received_requests.append(body)

        if self.responses:
            response_data = self.responses.pop(0)
        else:
            response_data = {"insert": [], "hasMore": False}

        return web.json_response(response_data)

    async def start(self) -> str:
        self._app = web.Application()
        self._app.router.add_post("/function", self.handle_request)

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()

        # Use port 0 for ephemeral port assignment
        self._site = web.TCPSite(self._runner, "127.0.0.1", 0)
        await self._site.start()

        # Get the actual port assigned
        _, self.port = self._runner.addresses[0]
        return f"http://127.0.0.1:{self.port}/function"

    async def stop(self) -> None:
        if self._runner:
            await self._runner.cleanup()


@pytest.fixture
async def mock_server() -> AsyncGenerator[MockFunctionServer, None]:
    server = MockFunctionServer()
    yield server
    await server.stop()


@pytest.mark.asyncio
async def test_sync_single_page(mock_server: MockFunctionServer) -> None:
    """Test sync with a single page of results (no pagination)."""
    mock_server.responses = [
        {
            "insert": [{"id": 1, "name": "Item 1"}, {"id": 2, "name": "Item 2"}],
            "hasMore": False,
        }
    ]

    url = await mock_server.start()

    async with httpx.AsyncClient() as http_client:
        client = CloudFunctionClient(
            agent="test-agent/ext-id/schema",
            http_client=http_client,
            function_url=url,
            secrets={"apiToken": "test-token"},
        )

        results: list[list[dict[str, Any]]] = []
        async for batch in client.sync("test-kind"):
            results.append(batch)

    assert len(results) == 1
    assert results[0] == [{"id": 1, "name": "Item 1"}, {"id": 2, "name": "Item 2"}]

    # Verify request payload
    assert len(mock_server.received_requests) == 1
    req = mock_server.received_requests[0]
    assert req["agent"] == "test-agent/ext-id/schema"
    assert req["kind"] == "test-kind"
    assert req["secrets"] == {"apiToken": "test-token"}


@pytest.mark.asyncio
async def test_sync_with_pagination(mock_server: MockFunctionServer) -> None:
    """Test sync with multiple pages of results."""
    mock_server.responses = [
        {
            "insert": [{"id": 1, "name": "Page 1 Item"}],
            "state": {"cursor": "abc123"},
            "hasMore": True,
        },
        {
            "insert": [{"id": 2, "name": "Page 2 Item"}],
            "state": {"cursor": "def456"},
            "hasMore": True,
        },
        {
            "insert": [{"id": 3, "name": "Page 3 Item"}],
            "hasMore": False,
        },
    ]

    url = await mock_server.start()

    async with httpx.AsyncClient() as http_client:
        client = CloudFunctionClient(
            agent="test-agent/ext-id/schema",
            http_client=http_client,
            function_url=url,
            secrets={},
        )

        results: list[list[dict[str, Any]]] = []
        async for batch in client.sync("paginated-kind"):
            results.append(batch)

    assert len(results) == 3
    assert results[0] == [{"id": 1, "name": "Page 1 Item"}]
    assert results[1] == [{"id": 2, "name": "Page 2 Item"}]
    assert results[2] == [{"id": 3, "name": "Page 3 Item"}]

    # Verify pagination state is passed correctly
    assert len(mock_server.received_requests) == 3
    assert mock_server.received_requests[0]["state"] is None
    assert mock_server.received_requests[1]["state"] == {"cursor": "abc123"}
    assert mock_server.received_requests[2]["state"] == {"cursor": "def456"}


@pytest.mark.asyncio
async def test_sync_empty_response(mock_server: MockFunctionServer) -> None:
    """Test sync with empty results."""
    mock_server.responses = [{"insert": [], "hasMore": False}]

    url = await mock_server.start()

    async with httpx.AsyncClient() as http_client:
        client = CloudFunctionClient(
            agent="test-agent",
            http_client=http_client,
            function_url=url,
            secrets={},
        )

        results: list[list[dict[str, Any]]] = []
        async for batch in client.sync("empty-kind"):
            results.append(batch)

    assert len(results) == 1
    assert results[0] == []
