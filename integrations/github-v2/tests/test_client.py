import time
from typing import Any
import pytest
from unittest.mock import patch, MagicMock
import httpx
from github.clients.rest_client import GithubRestClient
from port_ocean.context.event import event_context

TEST_DATA: dict[str, list[dict[str, Any]]] = {
    "repositories": [
        {"id": 1, "name": "repo1", "full_name": "test-org/repo1"},
        {"id": 2, "name": "repo2", "full_name": "test-org/repo2"},
    ]
}


@pytest.mark.asyncio
class TestGithubRestClient:

    async def test_create_or_update_webhook(
        self, client: GithubRestClient, mock_http_response: MagicMock
    ) -> None:
        mock_http_response.json.return_value = []
        create_hook_response = MagicMock()
        create_hook_response.json.return_value = {"id": "new-hook"}
        with patch(
            "port_ocean.utils.http_async_client.request",
            side_effect=[mock_http_response, create_hook_response],
        ):
            await client.create_or_update_webhook(client.base_url, ["event"])

        mock_http_response.json.return_value = [
            {
                "id": 1,
                "config": {
                    "url": f"{client.base_url}/integration/webhook",
                    "secret": "secret",
                },
            }
        ]
        with patch(
            "port_ocean.utils.http_async_client.request",
            return_value=mock_http_response,
        ):
            await client.create_or_update_webhook(client.base_url, ["event"])

    @pytest.mark.asyncio
    async def test_get_repositories(
        self, client: GithubRestClient, mock_http_response: MagicMock
    ) -> None:
        # First response: Non-empty data with next link
        first_response = mock_http_response
        first_response.headers["Link"] = (
            '<https://api.github.com/organizations/test/repos?page=2>; rel="next"'
        )
        first_response.json.return_value = TEST_DATA["repositories"]

        # Second response: Empty data, no next link
        second_response = MagicMock(spec=httpx.Response)
        second_response.status_code = 200
        second_response.headers = {
            "X-RateLimit-Remaining": "5000",
            "X-RateLimit-Reset": str(int(time.time()) + 3600),
            "Link": "",
        }
        second_response.json.return_value = []

        with patch(
            "port_ocean.utils.http_async_client.request",
            side_effect=[first_response, second_response],
        ):
            async with event_context("test_event"):
                repos: list[list[dict[str, Any]]] = [
                    batch async for batch in client.get_repositories()
                ]
                assert len(repos) == 1
                assert len(repos[0]) == 2
                assert repos[0] == TEST_DATA["repositories"]

    async def test_send_api_request_403(self, client: GithubRestClient) -> None:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 403
        mock_response.text = '{"message": "Forbidden"}'
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Forbidden", request=MagicMock(), response=mock_response
        )
        with patch(
            "port_ocean.utils.http_async_client.request", return_value=mock_response
        ):
            with pytest.raises(httpx.HTTPStatusError):
                await client._send_api_request("forbidden/endpoint")

    @pytest.mark.asyncio
    async def test_get_repositories_caching(
        self, client: GithubRestClient, mock_http_response: MagicMock
    ) -> None:
        mock_http_response.json.side_effect = [TEST_DATA["repositories"], []]
        # Second response: Empty data, no next link
        second_response = MagicMock(spec=httpx.Response)
        second_response.status_code = 200
        second_response.headers = {
            "X-RateLimit-Remaining": "5000",
            "X-RateLimit-Reset": str(int(time.time()) + 3600),
        }
        second_response.json.return_value = []

        with patch(
            "port_ocean.utils.http_async_client.request",
            return_value=mock_http_response,
        ) as mock_request:
            async with event_context("test_event"):
                # First call: fetches from API and caches
                repos1: list[list[dict[str, Any]]] = [
                    batch async for batch in client.get_repositories()
                ]
                # Second call: should use cache
                repos2: list[list[dict[str, Any]]] = [
                    batch async for batch in client.get_repositories()
                ]

            assert repos1 == repos2
            assert len(repos1) == 1
            assert len(repos1[0]) == 2
            assert mock_request.call_count == 1
