from typing import Any
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from github.clients.rest_client import GithubRestClient

TEST_DATA: dict[str, list[dict[str, Any]]] = {
    "repositories": [
        {"id": 1, "name": "repo1", "full_name": "test-org/repo1"},
        {"id": 2, "name": "repo2", "full_name": "test-org/repo2"},
    ]
}


@pytest.mark.asyncio
class TestGithubRestClient:

    async def test_send_paginated_request_single_page(self) -> None:
        client = GithubRestClient(
            token="test-token",
            organization="test-org",
            github_host="https://api.github.com",
        )

        # Mock response with no next link
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = [{"id": 1, "name": "repo1"}]
        mock_response.headers = {"Link": ""}

        with patch.object(
            client, "send_api_request", AsyncMock(return_value=mock_response)
        ):
            results = []
            async for page in client.send_paginated_request("orgs/test-org/repos"):
                results.append(page)

            assert len(results) == 1
            assert results[0] == [{"id": 1, "name": "repo1"}]

    @pytest.mark.asyncio
    async def test_send_paginated_request_multiple_pages(self) -> None:
        client = GithubRestClient(
            token="test-token",
            organization="test-org",
            github_host="https://api.github.com",
        )

        # First response with next link
        first_response = MagicMock(spec=httpx.Response)
        first_response.status_code = 200
        first_response.json.return_value = [{"id": 1, "name": "repo1"}]
        first_response.headers = {
            "Link": '<https://api.github.com/orgs/test-org/repos?page=2>; rel="next"'
        }

        # Second response with no next link
        second_response = MagicMock(spec=httpx.Response)
        second_response.status_code = 200
        second_response.json.return_value = [{"id": 2, "name": "repo2"}]
        second_response.headers = {"Link": ""}

        with patch.object(
            client,
            "send_api_request",
            AsyncMock(side_effect=[first_response, second_response]),
        ):
            results = []
            async for page in client.send_paginated_request("orgs/test-org/repos"):
                results.append(page)

            assert len(results) == 2
            assert results[0] == [{"id": 1, "name": "repo1"}]
            assert results[1] == [{"id": 2, "name": "repo2"}]

    @pytest.mark.asyncio
    async def test_send_paginated_request_empty_response(self) -> None:
        client = GithubRestClient(
            token="test-token",
            organization="test-org",
            github_host="https://api.github.com",
        )

        # Mock response with empty results
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_response.headers = {"Link": ""}

        with patch.object(
            client, "send_api_request", AsyncMock(return_value=mock_response)
        ):
            results = []
            async for page in client.send_paginated_request("orgs/test-org/repos"):
                results.append(page)

            assert len(results) == 0

    @pytest.mark.asyncio
    async def test_send_paginated_request_with_params(self) -> None:
        client = GithubRestClient(
            token="test-token",
            organization="test-org",
            github_host="https://api.github.com",
        )

        custom_params = {"type": "public"}

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = [{"id": 1, "name": "repo1"}]
        mock_response.headers = {"Link": ""}

        with patch.object(
            client, "send_api_request", AsyncMock(return_value=mock_response)
        ) as mock_send:
            results = []
            async for page in client.send_paginated_request(
                "orgs/test-org/repos", params=custom_params
            ):
                results.append(page)

            # Verify params were passed with per_page added
            expected_params = {"type": "public", "per_page": 100}
            mock_send.assert_called_once_with(
                "orgs/test-org/repos", method="GET", params=expected_params
            )
