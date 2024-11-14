import asyncio
import gitlab
from unittest.mock import AsyncMock, patch, MagicMock
from core.async_fetcher import AsyncFetcher

@patch("gitlab.Gitlab")
async def test_get_gitlab_client(mock_gitlab):
    url = "https://gitlab.example.com"
    token = "my_token"
    await AsyncFetcher.get_gitlab_client(url, token)
    mock_gitlab.assert_called_once_with(url, private_token=token, api_version="4")

@patch("asyncio.get_event_loop")
async def test_fetch_single(mock_loop):
    mock_loop.return_value.run_in_executor = AsyncMock()
    mock_fetch_method = MagicMock()
    args = (1, 2)
    kwargs = {"key": "value"}
    await AsyncFetcher.fetch_single(mock_fetch_method, *args, **kwargs)
    mock_loop.return_value.run_in_executor.assert_called_once_with(None, mock_fetch_method, *args, **kwargs)