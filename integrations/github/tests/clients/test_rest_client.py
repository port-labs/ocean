from typing import Any, List, Dict
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from github.clients.auth.abstract_authenticator import AbstractGitHubAuthenticator
from github.clients.http.rest_client import GithubRestClient

TEST_DATA: dict[str, list[dict[str, Any]]] = {
    "repositories": [
        {"id": 1, "name": "repo1", "full_name": "test-org/repo1"},
        {"id": 2, "name": "repo2", "full_name": "test-org/repo2"},
    ]
}


@pytest.fixture
def rest_client() -> GithubRestClient:
    return GithubRestClient(
        token="test-token",
        organization="test-org",
        github_host="https://api.github.com",
        authenticator=MagicMock(spec=AbstractGitHubAuthenticator),
    )


@pytest.mark.asyncio
class TestGithubRestClient:
    async def test_send_paginated_request_single_page(
        self, rest_client: GithubRestClient
    ) -> None:
        client = rest_client

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
    async def test_send_paginated_request_multiple_pages(
        self, rest_client: GithubRestClient
    ) -> None:
        client = rest_client

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
    async def test_send_paginated_request_empty_response(
        self, rest_client: GithubRestClient
    ) -> None:
        client = rest_client

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
    async def test_send_paginated_request_with_params(
        self, rest_client: GithubRestClient
    ) -> None:
        client = rest_client

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
                "orgs/test-org/repos",
                method="GET",
                params=expected_params,
                return_full_response=True,
            )

    @pytest.mark.parametrize(
        "response_data,expected_items",
        [([{"id": 1}], [{"id": 1}]), ({"id": 2}, [{"id": 2}]), ({}, []), ([], [])],
    )
    async def test_send_paginated_request_with_response_object(
        self,
        rest_client: GithubRestClient,
        response_data: Any,
        expected_items: List[Dict[str, Any]],
    ) -> None:
        # Mock the response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.headers = {}
        mock_response.json.return_value = response_data

        # Mock send_api_request to return our mock response
        with patch.object(
            rest_client, "send_api_request", new=AsyncMock(return_value=mock_response)
        ):
            # Collect all items from the paginated request
            items = []
            async for page in rest_client.send_paginated_request("test/resource"):
                if isinstance(page, dict):
                    items.append(page)
                else:
                    items.extend(page)

        # Verify the results
        assert items == expected_items

    async def test_send_paginated_request_with_pagination(
        self, rest_client: GithubRestClient
    ) -> None:
        # Mock responses for multiple pages
        mock_response1 = MagicMock(spec=httpx.Response)
        mock_response1.json.return_value = [{"id": 1}, {"id": 2}]
        mock_response1.headers = {
            "Link": '<https://api.github.com/test/resource?page=2>; rel="next"'
        }

        mock_response2 = MagicMock(spec=httpx.Response)
        mock_response2.json.return_value = [{"id": 3}, {"id": 4}]
        mock_response2.headers = {}

        # Mock send_api_request to return different responses for each call
        with patch.object(
            rest_client,
            "send_api_request",
            AsyncMock(side_effect=[mock_response1, mock_response2]),
        ) as mock_send:
            # Collect all items from the paginated request
            items = []
            async for page in rest_client.send_paginated_request("test/resource"):
                items.extend(page)

            # Verify we got all items from both pages
            assert items == [{"id": 1}, {"id": 2}, {"id": 3}, {"id": 4}]

            # Verify send_api_request was called twice
            assert mock_send.call_count == 2

    async def test_send_paginated_request_with_empty_page(
        self, rest_client: GithubRestClient
    ) -> None:
        # Mock response with empty page
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = []
        mock_response.headers = {}

        # Mock send_api_request
        with patch.object(
            rest_client, "send_api_request", AsyncMock(return_value=mock_response)
        ) as mock_send:
            # Collect all items from the paginated request
            items = []
            async for page in rest_client.send_paginated_request("test/resource"):
                items.extend(page)

            # Verify we got no items
            assert items == []

            # Verify send_api_request was called once
            mock_send.assert_called_once()

    async def test_send_paginated_request_with_single_empty_dict(
        self, rest_client: GithubRestClient
    ) -> None:
        # Mock response with single empty dict
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = []
        mock_response.headers = {}

        # Mock send_api_request
        with patch.object(
            rest_client, "send_api_request", AsyncMock(return_value=mock_response)
        ) as mock_send:
            items = []
            async for page in rest_client.send_paginated_request("test/resource"):
                items.extend(page)

            # Verify we got no items (empty dict page should be skipped)
            assert items == []

            # Verify send_api_request was called once
            mock_send.assert_called_once()
