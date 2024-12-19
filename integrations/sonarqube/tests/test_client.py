from typing import Any
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from client import SonarQubeClient, turn_sequence_to_chunks

from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Fixture to mock the Ocean context initialization."""
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = {
            "sonarqube_host": "https://example.sonarqube.com",
            "sonarqube_token": "test_token",
            "organization_id": "test_org",
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.mark.parametrize(
    "input, output, chunk_size",
    [
        ([1, 2, 4], [[1], [2], [4]], 1),
        ([1, 2, 4], [[1, 2], [4]], 2),
        ([1, 2, 3, 4, 5, 6, 7], [[1, 2, 3, 4, 5, 6, 7]], 7),
        ([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], [[1, 2], [3, 4], [5, 6], [7, 8], [9, 10]], 2),
    ],
)
def test_turn_sequence_to_chunks(
    input: list[Any], output: list[list[Any]], chunk_size: int
) -> None:
    assert list(turn_sequence_to_chunks(input, chunk_size)) == output


@pytest.mark.asyncio
async def test_pagination() -> None:
    client = SonarQubeClient("http://test", "token", None, None)

    mock_responses = [
        httpx.Response(
            200,
            json={
                "components": [{"id": "1"}],
                "paging": {"pageIndex": 1, "pageSize": 1, "total": 2},
            },
            request=httpx.Request("GET", "/"),
        ),
        httpx.Response(
            200,
            json={
                "components": [{"id": "2"}],
                "paging": {"pageIndex": 2, "pageSize": 1, "total": 2},
            },
            request=httpx.Request("GET", "/"),
        ),
    ]

    with patch.object(
        client.http_client, "request", AsyncMock(side_effect=mock_responses)
    ):
        result = await client.send_paginated_api_request("test", "components")
        assert len(result) == 2


@pytest.mark.asyncio
async def test_pagination_partial_response() -> None:
    client = SonarQubeClient("http://test", "token", None, None)

    mock_responses = [
        httpx.Response(
            200,
            json={
                "components": [{"id": i} for i in range(3)],
                "paging": {"pageIndex": 1, "pageSize": 3, "total": 4},
            },
            request=httpx.Request("GET", "/"),
        ),
        httpx.Response(
            200,
            json={
                "components": [{"id": 3}],
                "paging": {"pageIndex": 2, "pageSize": 3, "total": 4},
            },
            request=httpx.Request("GET", "/"),
        ),
    ]

    with patch.object(
        client.http_client, "request", AsyncMock(side_effect=mock_responses)
    ):
        result = await client.send_paginated_api_request("test", "components")
        assert len(result) == 4