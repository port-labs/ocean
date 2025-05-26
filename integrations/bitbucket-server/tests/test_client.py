from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient, Response

from client import BitbucketClient


@pytest.fixture
def mock_client() -> BitbucketClient:
    """Create a mocked Bitbucket Server client."""
    client = BitbucketClient(
        base_url="https://bitbucket.example.com",
        username="test-user",
        password="test-password",
        webhook_secret="test-secret",
        app_host="https://app.example.com",
    )
    client.client = MagicMock(spec=AsyncClient)
    return client


@pytest.mark.asyncio
async def test_send_port_request(mock_client: BitbucketClient) -> None:
    """Test sending a request to the Bitbucket API."""
    # Arrange
    expected_response = {"key": "TEST", "name": "Test Project"}
    mock_response = MagicMock(spec=Response)
    mock_response.json = MagicMock(return_value=expected_response)
    mock_response.raise_for_status = MagicMock()
    mock_client.client.request.return_value = mock_response  # type: ignore[attr-defined]

    # Act
    response = await mock_client._send_api_request("GET", "projects/TEST")

    # Assert
    assert response == expected_response
    mock_client.client.request.assert_called_once()  # type: ignore[attr-defined]
    mock_response.raise_for_status.assert_called_once()


@pytest.mark.asyncio
async def test_get_paginated_resource(mock_client: BitbucketClient) -> None:
    """Test getting paginated resources from the Bitbucket API."""
    # Arrange
    mock_responses = [
        {
            "values": [{"id": 1}, {"id": 2}],
            "isLastPage": False,
        },
        {
            "values": [{"id": 3}],
            "isLastPage": True,
        },
    ]
    mock_client._send_api_request = AsyncMock(side_effect=mock_responses)  # type: ignore[method-assign]

    # Act
    results = []
    async for batch in mock_client.get_paginated_resource("projects"):
        results.extend(batch)

    # Assert
    assert len(results) == 3
    assert [r["id"] for r in results] == [1, 2, 3]
    assert mock_client._send_api_request.call_count == 2


@pytest.mark.asyncio
async def test_healthcheck(mock_client: BitbucketClient) -> None:
    """Test health check functionality."""
    # Arrange
    mock_client._get_application_properties = AsyncMock(  # type: ignore[method-assign]
        return_value={"version": "8.8.0"}
    )

    # Act & Assert
    await mock_client.healthcheck()  # Should not raise an exception


@pytest.mark.asyncio
async def test_healthcheck_failure(mock_client: BitbucketClient) -> None:
    """Test health check failure."""
    # Arrange
    mock_client._get_application_properties = AsyncMock(  # type: ignore[method-assign]
        side_effect=Exception("Connection failed")
    )
    # Act & Assert
    with pytest.raises(ConnectionError):
        await mock_client.healthcheck()
