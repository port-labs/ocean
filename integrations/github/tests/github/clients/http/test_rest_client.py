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


def _http_error(status_code: int) -> httpx.HTTPStatusError:
    """Build an HTTPStatusError as raised by make_request for a given status."""
    request = httpx.Request("GET", "https://api.github.com/test/resource")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError(
        f"{status_code} error", request=request, response=response
    )


def _http_500() -> httpx.HTTPStatusError:
    return _http_error(500)


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
            client, "make_request", AsyncMock(return_value=mock_response)
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
            "make_request",
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
            client, "make_request", AsyncMock(return_value=mock_response)
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
            client, "make_request", AsyncMock(return_value=mock_response)
        ) as mock_send:
            results = []
            async for page in client.send_paginated_request(
                "orgs/test-org/repos", params=custom_params
            ):
                results.append(page)

            # Verify params were passed with page and per_page added
            expected_params = {"type": "public", "page": 1, "per_page": 100}
            mock_send.assert_called_once_with(
                "orgs/test-org/repos",
                method="GET",
                params=expected_params,
                ignored_errors=None,
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

        # Mock make_request to return our mock response
        with patch.object(
            rest_client, "make_request", new=AsyncMock(return_value=mock_response)
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

        # Mock make_request to return different responses for each call
        with patch.object(
            rest_client,
            "make_request",
            AsyncMock(side_effect=[mock_response1, mock_response2]),
        ) as mock_send:
            # Collect all items from the paginated request
            items = []
            async for page in rest_client.send_paginated_request("test/resource"):
                items.extend(page)

            # Verify we got all items from both pages
            assert items == [{"id": 1}, {"id": 2}, {"id": 3}, {"id": 4}]

            # Verify make_request was called twice
            assert mock_send.call_count == 2

    async def test_send_paginated_request_with_empty_page(
        self, rest_client: GithubRestClient
    ) -> None:
        # Mock response with empty page
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = []
        mock_response.headers = {}

        # Mock make_request
        with patch.object(
            rest_client, "make_request", AsyncMock(return_value=mock_response)
        ) as mock_send:
            # Collect all items from the paginated request
            items = []
            async for page in rest_client.send_paginated_request("test/resource"):
                items.extend(page)

            # Verify we got no items
            assert items == []

            # Verify make_request was called once
            mock_send.assert_called_once()

    async def test_send_paginated_request_with_single_empty_dict(
        self, rest_client: GithubRestClient
    ) -> None:
        # Mock response with single empty dict
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = []
        mock_response.headers = {}

        # Mock make_request
        with patch.object(
            rest_client, "make_request", AsyncMock(return_value=mock_response)
        ) as mock_send:
            items = []
            async for page in rest_client.send_paginated_request("test/resource"):
                items.extend(page)

            # Verify we got no items (empty dict page should be skipped)
            assert items == []

            # Verify make_request was called once
            mock_send.assert_called_once()

    async def test_send_paginated_request_halves_page_size_on_500(
        self, rest_client: GithubRestClient
    ) -> None:
        # First request (page=1, per_page=100) fails with a 500
        # Retry should resume at page=1, per_page=50 and succeed.
        success_response = MagicMock(spec=httpx.Response)
        success_response.json.return_value = [{"id": 1}, {"id": 2}]
        success_response.headers = {}

        with patch.object(
            rest_client,
            "make_request",
            AsyncMock(side_effect=[_http_500(), success_response]),
        ) as mock_send:
            items = []
            async for page in rest_client.send_paginated_request("test/resource"):
                items.extend(page)

            assert items == [{"id": 1}, {"id": 2}]
            assert mock_send.call_count == 2

            first_params = mock_send.call_args_list[0].kwargs["params"]
            assert first_params["page"] == 1
            assert first_params["per_page"] == 100

            retry_params = mock_send.call_args_list[1].kwargs["params"]
            # 2 * 1 - 1 == 1, so we re-fetch from the same offset at half size
            assert retry_params["page"] == 1
            assert retry_params["per_page"] == 50
            # per_page must stay an int, not become 50.0
            assert isinstance(retry_params["per_page"], int)

    async def test_send_paginated_request_resumes_at_correct_offset_on_500(
        self, rest_client: GithubRestClient
    ) -> None:
        # Page 1 succeeds (per_page=100) with a next link, page 2 fails with 500.
        # Retry must resume at page=3, per_page=50 (items 101-150) — no gaps/dupes.
        first_response = MagicMock(spec=httpx.Response)
        first_response.json.return_value = [{"id": 1}]
        first_response.headers = {
            "Link": '<https://api.github.com/test/resource?page=2>; rel="next"'
        }

        retry_response = MagicMock(spec=httpx.Response)
        retry_response.json.return_value = [{"id": 101}]
        retry_response.headers = {}

        with patch.object(
            rest_client,
            "make_request",
            AsyncMock(side_effect=[first_response, _http_500(), retry_response]),
        ) as mock_send:
            items = []
            async for page in rest_client.send_paginated_request("test/resource"):
                items.extend(page)

            assert items == [{"id": 1}, {"id": 101}]
            assert mock_send.call_count == 3

            failed_params = mock_send.call_args_list[1].kwargs["params"]
            assert failed_params["page"] == 2
            assert failed_params["per_page"] == 100

            retry_params = mock_send.call_args_list[2].kwargs["params"]
            assert retry_params["page"] == 3
            assert retry_params["per_page"] == 50

    async def test_send_paginated_request_raises_at_page_size_floor(
        self, rest_client: GithubRestClient
    ) -> None:
        # Persistent 500s: 100 -> 50 -> 25, then re-raise once at/below the floor.
        with patch.object(
            rest_client,
            "make_request",
            AsyncMock(side_effect=[_http_500(), _http_500(), _http_500()]),
        ) as mock_send:
            with pytest.raises(httpx.HTTPStatusError):
                async for _ in rest_client.send_paginated_request("test/resource"):
                    pass

            per_page_values = [
                call.kwargs["params"]["per_page"] for call in mock_send.call_args_list
            ]
            assert per_page_values == [100, 50, 25]

    async def test_send_paginated_request_reraises_non_500_error(
        self, rest_client: GithubRestClient
    ) -> None:
        # Non-500 errors must propagate immediately without any backoff/retry.
        with patch.object(
            rest_client,
            "make_request",
            AsyncMock(side_effect=_http_error(503)),
        ) as mock_send:
            with pytest.raises(httpx.HTTPStatusError):
                async for _ in rest_client.send_paginated_request("test/resource"):
                    pass

            mock_send.assert_called_once()
