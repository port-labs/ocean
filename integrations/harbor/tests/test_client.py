"""Unit tests for HarborClient."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import Request, Response

from harbor.clients.http.client import HarborClient
from harbor.core.exporters.abstract_exporter import AbstractHarborExporter


@pytest.mark.asyncio
async def test_client_initialization(mock_harbor_client: HarborClient) -> None:
    """Test the correct initialization of HarborClient with authentication."""
    assert mock_harbor_client.base_url == "https://harbor.example.com"
    assert mock_harbor_client.username == "test_user"
    assert mock_harbor_client.password == "test_password"


@pytest.mark.asyncio
async def test_client_initialization_no_auth() -> None:
    """Test that HarborClient requires authentication credentials."""
    # Test that missing username raises ValueError
    with pytest.raises(ValueError, match="Username is required"):
        HarborClient(
            base_url="https://harbor.example.com",
            username="",  # Empty username
            password="test_password",
        )
    
    # Test that missing password raises ValueError
    with pytest.raises(ValueError, match="Password is required"):
        HarborClient(
            base_url="https://harbor.example.com",
            username="test_user",
            password="",  # Empty password
        )


@pytest.mark.asyncio
async def test_api_base_url_property(mock_harbor_client: HarborClient) -> None:
    """Test the api_base_url property."""
    assert mock_harbor_client.api_base_url == "https://harbor.example.com/api/v2.0"


@pytest.mark.asyncio
async def test_get_auth_headers(mock_harbor_client: HarborClient) -> None:
    """Test that _get_auth_headers returns correct Basic Auth headers."""
    headers = mock_harbor_client._get_auth_headers()
    
    assert "Authorization" in headers
    assert headers["Authorization"].startswith("Basic ")
    assert "Content-Type" in headers
    assert headers["Content-Type"] == "application/json"
    assert "Accept" in headers
    assert headers["Accept"] == "application/json"


@pytest.mark.asyncio
async def test_send_api_request_success(mock_harbor_client: HarborClient) -> None:
    """Test successful API requests."""
    with patch("port_ocean.utils.http_async_client.request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = Response(
            200,
            request=Request("GET", "http://example.com"),
            json={"key": "value"},
        )
        response = await mock_harbor_client.send_api_request(
            "projects"
        )
        assert response["key"] == "value"


@pytest.mark.asyncio
async def test_send_api_request_failure(mock_harbor_client: HarborClient) -> None:
    """Test API request raising exceptions for errors."""
    with patch("port_ocean.utils.http_async_client.request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = Response(
            404, request=Request("GET", "http://example.com")
        )
        with pytest.raises(Exception):
            await mock_harbor_client.send_api_request("projects")


@pytest.mark.asyncio
async def test_extract_items_from_response_list() -> None:
    """Test extracting items from a list response."""
    response = [{"id": 1}, {"id": 2}]
    items = AbstractHarborExporter._extract_items_from_response(response)
    assert items == [{"id": 1}, {"id": 2}]


@pytest.mark.asyncio
async def test_extract_items_from_response_dict_with_items() -> None:
    """Test extracting items from a dict response with 'items' key."""
    response = {"items": [{"id": 1}, {"id": 2}], "total": 2}
    items = AbstractHarborExporter._extract_items_from_response(response)
    assert items == [{"id": 1}, {"id": 2}]


@pytest.mark.asyncio
async def test_extract_items_from_response_dict_with_data() -> None:
    """Test extracting items from a dict response with 'data' key."""
    response = {"data": [{"id": 1}, {"id": 2}]}
    items = AbstractHarborExporter._extract_items_from_response(response)
    assert items == [{"id": 1}, {"id": 2}]


@pytest.mark.asyncio
async def test_extract_items_from_response_empty() -> None:
    """Test extracting items from an empty or invalid response."""
    response: dict[str, Any] = {}
    items = AbstractHarborExporter._extract_items_from_response(response)
    assert items == []


@pytest.mark.asyncio
async def test_send_paginated_request(mock_harbor_client: HarborClient) -> None:
    """Test paginated resource fetching."""
    with patch.object(
        mock_harbor_client, "_make_request", new_callable=AsyncMock
    ) as mock_request:
        # First page with full results (exactly PAGE_SIZE), second page with fewer results
        PAGE_SIZE = HarborClient.PAGE_SIZE
        
        first_page = [{"id": i} for i in range(1, PAGE_SIZE + 1)]  # Exactly PAGE_SIZE items
        second_page = [{"id": PAGE_SIZE + 1}]  # Less than PAGE_SIZE, should stop pagination
        
        mock_request.side_effect = [
            Response(200, request=Request("GET", "http://example.com"), json=first_page),
            Response(200, request=Request("GET", "http://example.com"), json=second_page),
        ]

        results = []
        async for batch in mock_harbor_client.send_paginated_request(
            "projects",
        ):
            results.extend(batch)

        assert len(results) == PAGE_SIZE + 1
        assert results[0]["id"] == 1
        assert results[PAGE_SIZE]["id"] == PAGE_SIZE + 1
        assert mock_request.call_count == 2


@pytest.mark.asyncio
async def test_send_paginated_request_empty_response(
    mock_harbor_client: HarborClient,
) -> None:
    """Test paginated resource fetching with empty first page."""
    with patch.object(
        mock_harbor_client, "_make_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = Response(
            200, request=Request("GET", "http://example.com"), json=[]
        )

        results = []
        async for batch in mock_harbor_client.send_paginated_request(
            "projects"
        ):
            results.extend(batch)

        assert len(results) == 0
        assert mock_request.call_count == 1


@pytest.mark.asyncio
async def test_send_paginated_request_with_params(
    mock_harbor_client: HarborClient,
) -> None:
    """Test paginated resources with custom parameters."""
    with patch.object(
        mock_harbor_client, "_make_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [
            Response(200, request=Request("GET", "http://example.com"), json=[{"id": 1}]),
            Response(200, request=Request("GET", "http://example.com"), json=[]),  # Empty response to stop pagination
        ]

        results = []
        async for batch in mock_harbor_client.send_paginated_request(
            "projects",
            params={"public": "true"},
        ):
            results.extend(batch)

        # Verify params were passed correctly
        call_args = mock_request.call_args_list[0]
        assert call_args[1]["params"]["public"] == "true"
        assert call_args[1]["params"]["page"] == 1
        # PAGE_SIZE default is 50
        assert call_args[1]["params"]["page_size"] == 50
