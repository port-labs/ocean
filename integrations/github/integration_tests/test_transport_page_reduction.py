"""Integration tests for the transport-layer page-size backoff.

GitHub returns intermittent 5xx on large pages. GitHubRetryTransport recovers by
shrinking the page before each retry — halving REST `per_page` and stepping down
GraphQL `variables.first` — until the page succeeds or reaches its floor.

The full resync harness installs the raw InterceptTransport and bypasses
GitHubRetryTransport, so these tests wire a real client to an InterceptTransport
with the production retry transport back in the chain (by patching the innermost
httpx.AsyncHTTPTransport that OceanAsyncClient wraps), then drive real paginated
requests and assert on the page sizes the transport actually sent.
"""

import json
from collections.abc import Iterator
from typing import Any, Callable
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError
from port_ocean.integration_testing import InterceptTransport

from github.clients.auth.personal_access_token_authenticator import (
    PersonalTokenAuthenticator,
)
from github.clients.http.graphql_client import GithubGraphQLClient
from github.clients.http.rest_client import GithubRestClient

HOST = "https://api.github.com"
ORG = "test-org"


@pytest.fixture(autouse=True)
def _ocean_context() -> None:
    app = MagicMock()
    app.is_saas = MagicMock(return_value=False)
    app.config.client_timeout = 30
    try:
        initialize_port_ocean_context(app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.fixture
def wire_transport() -> Iterator[Callable[[InterceptTransport], None]]:
    """Route real clients through an InterceptTransport wrapped by the retry transport.

    Patches the innermost httpx.AsyncHTTPTransport that OceanAsyncClient builds so
    that GitHubRetryTransport wraps our InterceptTransport, and stubs the retry
    sleep so the backoff walk runs instantly.
    """
    patches = []

    def _wire(intercept: InterceptTransport) -> None:
        p_transport = patch(
            "port_ocean.helpers.async_client.httpx.AsyncHTTPTransport",
            side_effect=lambda **_: intercept,
        )
        p_sleep = patch("port_ocean.helpers.retry.asyncio.sleep", new=AsyncMock())
        p_transport.start()
        p_sleep.start()
        patches.extend([p_transport, p_sleep])

    yield _wire

    for p in patches:
        p.stop()


def _authenticator() -> PersonalTokenAuthenticator:
    return PersonalTokenAuthenticator("test-token")


def _graphql_success(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "status_code": 200,
        "json": {
            "data": {
                "organization": {
                    "repositories": {
                        "nodes": nodes,
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            }
        },
    }


async def _drain_graphql(client: GithubGraphQLClient) -> list[list[dict[str, Any]]]:
    return [
        page
        async for page in client.send_paginated_request(
            "query", params={"__path": "organization.repositories"}
        )
    ]


async def _drain_rest(client: GithubRestClient, resource: str) -> list[Any]:
    return [batch async for batch in client.send_paginated_request(resource)]


class TestGraphQLTransportReduction:
    @pytest.mark.asyncio
    async def test_5xx_steps_down_first_until_success(
        self, wire_transport: Callable[[InterceptTransport], None]
    ) -> None:
        sent_first: list[int] = []

        def respond(request: httpx.Request) -> dict[str, Any]:
            first = json.loads(request.content)["variables"]["first"]
            sent_first.append(first)
            if first > 15:
                return {"status_code": 502, "json": {"message": "boom"}}
            return _graphql_success([{"id": 1}])

        intercept = InterceptTransport(strict=False)
        intercept.add_route("POST", lambda r: "/graphql" in str(r.url), respond)
        wire_transport(intercept)

        client = GithubGraphQLClient(
            organization=ORG, github_host=HOST, authenticator=_authenticator()
        )
        pages = await _drain_graphql(client)

        assert pages == [[{"id": 1}]]
        # 25 fails, 20 fails, 15 succeeds — each size tried once, no replays.
        assert sent_first == [25, 20, 15]

    @pytest.mark.asyncio
    async def test_5xx_at_floor_stops_and_raises(
        self, wire_transport: Callable[[InterceptTransport], None]
    ) -> None:
        sent_first: list[int] = []

        def respond(request: httpx.Request) -> dict[str, Any]:
            sent_first.append(json.loads(request.content)["variables"]["first"])
            return {"status_code": 500, "json": {"message": "boom"}}

        intercept = InterceptTransport(strict=False)
        intercept.add_route("POST", lambda r: "/graphql" in str(r.url), respond)
        wire_transport(intercept)

        client = GithubGraphQLClient(
            organization=ORG, github_host=HOST, authenticator=_authenticator()
        )
        with pytest.raises(httpx.HTTPStatusError):
            await _drain_graphql(client)

        # 25 -> 20 -> 15 -> 10 -> 5 -> 1, then the floor stops further retries.
        assert sent_first == [25, 20, 15, 10, 5, 1]


class TestRestTransportReduction:
    @pytest.mark.asyncio
    async def test_5xx_halves_per_page_until_success(
        self, wire_transport: Callable[[InterceptTransport], None]
    ) -> None:
        sent: list[tuple[int, int]] = []

        def respond(request: httpx.Request) -> dict[str, Any]:
            per_page = int(request.url.params["per_page"])
            page = int(request.url.params.get("page", 1))
            sent.append((page, per_page))
            if per_page > 25:
                return {"status_code": 500, "json": {"message": "boom"}}
            return {"status_code": 200, "json": [{"number": page}]}

        intercept = InterceptTransport(strict=False)
        intercept.add_route("GET", "/issues", respond)
        wire_transport(intercept)

        client = GithubRestClient(
            organization=ORG, github_host=HOST, authenticator=_authenticator()
        )
        batches = await _drain_rest(client, f"{HOST}/repos/{ORG}/r/issues")

        assert batches == [[{"number": 1}]]
        # 100 fails, 50 fails, 25 succeeds. The first page has no `page` param, so
        # the offset-preserving reposition (N -> 2N-1) keeps it at page 1 throughout.
        assert sent == [(1, 100), (1, 50), (1, 25)]

    @pytest.mark.asyncio
    async def test_5xx_at_floor_stops_and_raises(
        self, wire_transport: Callable[[InterceptTransport], None]
    ) -> None:
        sent: list[int] = []

        def respond(request: httpx.Request) -> dict[str, Any]:
            sent.append(int(request.url.params["per_page"]))
            return {"status_code": 500, "json": {"message": "boom"}}

        intercept = InterceptTransport(strict=False)
        intercept.add_route("GET", "/issues", respond)
        wire_transport(intercept)

        client = GithubRestClient(
            organization=ORG, github_host=HOST, authenticator=_authenticator()
        )
        with pytest.raises(httpx.HTTPStatusError):
            await _drain_rest(client, f"{HOST}/repos/{ORG}/r/issues")

        # 100 -> 50 -> 25, then the floor stops further retries.
        assert sent == [100, 50, 25]
