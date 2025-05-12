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
    ],
    "pull_requests": [
        {"id": 101, "number": 1, "title": "First PR", "state": "open"},
        {"id": 102, "number": 2, "title": "Second PR", "state": "closed"},
    ],
    "issues": [
        {"id": 201, "number": 1, "title": "Bug report", "state": "open"},
        {"id": 202, "number": 2, "title": "Feature request", "state": "closed"},
    ],
    "teams": [{"id": 1, "name": "team1"}],
    "workflows": [{"id": "wf1", "name": "Workflow1"}],
    "workflow_runs": [{"id": "run1", "status": "completed"}],
}


@pytest.mark.asyncio
class TestGithubRestClient:
    async def test_rate_limiting(
        self, client: GithubRestClient, mock_http_response: MagicMock
    ) -> None:
        mock_http_response.status_code = 429
        mock_http_response.headers.update(
            {
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(pytest.importorskip("time").time()) + 60),
            }
        )
        with patch(
            "port_ocean.utils.http_async_client.request",
            side_effect=[mock_http_response, MagicMock()],
        ):
            await client._send_api_request("/test")

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
        mock_http_response.json.side_effect = [
            TEST_DATA["repositories"],  # Page 1
            [],  # Page 2 (empty, stops pagination)
        ]

        with patch(
            "port_ocean.utils.http_async_client.request",
            return_value=mock_http_response,
        ):
            async with event_context("test_event"):
                repos: list[list[dict[str, Any]]] = [
                    batch async for batch in client.get_repositories()
                ]
                assert len(repos) == 1
                assert len(repos[0]) == 2
                assert repos[0] == TEST_DATA["repositories"]

    async def test_paginate_request_multiple_pages(
        self, client: GithubRestClient
    ) -> None:
        page1 = MagicMock()
        page1.json.return_value = TEST_DATA["repositories"]
        page2 = MagicMock()
        page2.json.return_value = []
        with patch(
            "port_ocean.utils.http_async_client.request", side_effect=[page1, page2]
        ):
            repos: list[list[dict[str, Any]]] = [
                batch
                async for batch in client._paginate_request(
                    f"orgs/{client.organization}/repos"
                )
            ]
            assert len(repos[0]) == 2

    async def test_send_api_request_403(self, client: GithubRestClient) -> None:
        mock_response = MagicMock()
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
            assert (
                mock_request.call_count == 2
            )  # Two calls: one for each page in first fetch
