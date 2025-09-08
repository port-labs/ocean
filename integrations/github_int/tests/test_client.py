# integrations/github/tests/test_client.py
# Example unit test (expand as needed)
import pytest
from unittest.mock import AsyncMock, patch

from github.client import GitHubClient

@pytest.mark.asyncio
async def test_send_api_request_rate_limit():
    client = GitHubClient(token="fake")
    with patch.object(client.client, 'request', new=AsyncMock()) as mock_request:
        mock_response = AsyncMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "1"}
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Rate limit", request=None, response=mock_response
        )
        mock_request.side_effect = [mock_response, AsyncMock(json=lambda: {"data": "ok"})]
        result = await client._send_api_request("GET", "test")
        assert result == {"data": "ok"}
        assert mock_request.call_count == 2

# Add to test_client.py

@pytest.mark.asyncio
async def test_get_folders():
    client = GitHubClient(token="fake")
    with patch.object(client, '_send_api_request', new_callable=AsyncMock) as mock_request:
        mock_tree = {
            "tree": [
                {"type": "tree", "path": "services/backend", "sha": "abc123", "url": "fake_url"},
                {"type": "blob", "path": "services/backend/file.py"}
            ]
        }
        mock_request.return_value = mock_tree
        mock_readme = {"content": "base64readme"}
        mock_request.side_effect = [mock_tree, mock_readme]  # Tree + README

        async for batch in client.get_folders("test/repo", 123, "main", paths=["services/"]):
            assert len(batch) == 1
            assert batch[0]["path"] == "services/backend"
            assert batch[0]["readme"] == "readme"  # Decoded