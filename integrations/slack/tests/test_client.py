import pytest
from unittest.mock import AsyncMock, patch
import aiohttp

from ..client import SlackApiClient


@pytest.mark.asyncio
async def test_rate_limit_handling():
    """Test rate limit handling in the Slack API client."""
    client = SlackApiClient("xoxb-test-token")

    # Mock rate limit response
    mock_response = AsyncMock()
    mock_response.status = 429
    mock_response.headers = {"Retry-After": "1"}
    mock_response.json = AsyncMock(return_value={"error": "rate_limited"})

    # Mock ClientSession
    mock_session = AsyncMock()
    mock_session.get.side_effect = [
        mock_response,  # First call gets rate limited
        AsyncMock(  # Second call succeeds
            status=200,
            json=AsyncMock(return_value={"ok": True, "channels": []})
        )
    ]

    with patch("aiohttp.ClientSession", return_value=mock_session):
        result = await client._make_request("GET", "conversations.list")

        # Verify rate limit handling
        assert mock_session.get.call_count == 2
        assert result == {"ok": True, "channels": []}


@pytest.mark.asyncio
async def test_error_handling():
    """Test error handling in the Slack API client."""
    client = SlackApiClient("xoxb-test-token")

    # Mock error response
    mock_response = AsyncMock()
    mock_response.status = 400
    mock_response.json = AsyncMock(return_value={"error": "invalid_auth"})

    # Mock ClientSession
    mock_session = AsyncMock()
    mock_session.get.return_value = mock_response

    with patch("aiohttp.ClientSession", return_value=mock_session):
        with pytest.raises(Exception) as exc_info:
            await client.get_channels()
        assert "invalid_auth" in str(exc_info.value)


@pytest.mark.asyncio
async def test_pagination_handling():
    """Test pagination handling in the Slack API client."""
    client = SlackApiClient("xoxb-test-token")

    # Mock paginated responses
    mock_responses = [
        AsyncMock(
            status=200,
            json=AsyncMock(return_value={
                "ok": True,
                "channels": [{"id": "C1"}],
                "response_metadata": {"next_cursor": "cursor1"}
            })
        ),
        AsyncMock(
            status=200,
            json=AsyncMock(return_value={
                "ok": True,
                "channels": [{"id": "C2"}],
                "response_metadata": {"next_cursor": ""}
            })
        )
    ]

    # Mock ClientSession
    mock_session = AsyncMock()
    mock_session.get.side_effect = mock_responses

    with patch("aiohttp.ClientSession", return_value=mock_session):
        result = await client.get_channels()

        # Verify pagination handling
        assert len(result) == 2
        assert result[0]["id"] == "C1"
        assert result[1]["id"] == "C2"
        assert mock_session.get.call_count == 2
