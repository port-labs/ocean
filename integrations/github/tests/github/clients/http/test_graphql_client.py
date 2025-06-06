import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from github.clients.auth.abstract_authenticator import AbstractGitHubAuthenticator
from github.clients.http.graphql_client import GithubGraphQLClient
from github.helpers.exceptions import GraphQLClientError


@pytest.mark.asyncio
class TestGithubGraphQLClient:
    async def test_handle_graphql_errors(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        client = GithubGraphQLClient(
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
        )

        # Mock response with GraphQL errors
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "errors": [
                {"message": "Error 1", "path": ["field1"]},
                {"message": "Error 2", "path": ["field2"]},
            ]
        }

        # Mock the client's configuration
        mock_config = MagicMock()
        mock_config.client_timeout = 30.0  # Set a proper float value for timeout

        with patch.object(
            client.authenticator.client,
            "request",
            AsyncMock(return_value=mock_response),
        ):
            with pytest.raises(ExceptionGroup) as exc_info:
                await client.send_api_request(
                    client.base_url, method="POST", json_data={}
                )

            # Verify the exception group
            assert str(exc_info.value) == "GraphQL errors occurred. (2 sub-exceptions)"
            assert len(exc_info.value.exceptions) == 2
            assert (
                str(exc_info.value.exceptions[0])
                == "{'message': 'Error 1', 'path': ['field1']}"
            )
            assert (
                str(exc_info.value.exceptions[1])
                == "{'message': 'Error 2', 'path': ['field2']}"
            )

    async def test_handle_graphql_success(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        client = GithubGraphQLClient(
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
        )

        # Mock successful response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "organization": {
                    "repositories": {
                        "nodes": [{"id": 1, "name": "repo1"}],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            }
        }

        with patch.object(
            client, "send_api_request", AsyncMock(return_value=mock_response)
        ):
            response = await client.send_api_request(
                client.base_url, method="POST", json_data={}
            )
            assert response.json()["data"]["organization"]["repositories"]["nodes"] == [
                {"id": 1, "name": "repo1"}
            ]

    async def test_send_paginated_request_single_page(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        client = GithubGraphQLClient(
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
        )

        # Mock response with no next page
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "organization": {
                    "repositories": {
                        "nodes": [{"id": 1, "name": "repo1"}],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            }
        }

        with patch.object(
            client, "send_api_request", AsyncMock(return_value=mock_response)
        ):
            results = []
            async for page in client.send_paginated_request(
                "query", params={"__path": "organization.repositories"}
            ):
                results.append(page)

            assert len(results) == 1
            assert results[0] == [{"id": 1, "name": "repo1"}]

    async def test_send_paginated_request_multiple_pages(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        client = GithubGraphQLClient(
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
        )

        # First response with next page
        first_response = MagicMock(spec=httpx.Response)
        first_response.status_code = 200
        first_response.json.return_value = {
            "data": {
                "organization": {
                    "repositories": {
                        "nodes": [{"id": 1, "name": "repo1"}],
                        "pageInfo": {"hasNextPage": True, "endCursor": "cursor1"},
                    }
                }
            }
        }

        # Second response with no next page
        second_response = MagicMock(spec=httpx.Response)
        second_response.status_code = 200
        second_response.json.return_value = {
            "data": {
                "organization": {
                    "repositories": {
                        "nodes": [{"id": 2, "name": "repo2"}],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            }
        }

        with patch.object(
            client,
            "send_api_request",
            AsyncMock(side_effect=[first_response, second_response]),
        ):
            results = []
            async for page in client.send_paginated_request(
                "query", params={"__path": "organization.repositories"}
            ):
                results.append(page)

            assert len(results) == 2
            assert results[0] == [{"id": 1, "name": "repo1"}]
            assert results[1] == [{"id": 2, "name": "repo2"}]

    async def test_send_paginated_request_empty_response(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        client = GithubGraphQLClient(
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
        )

        # Mock response with empty nodes
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "organization": {
                    "repositories": {
                        "nodes": [],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            }
        }

        with patch.object(
            client, "send_api_request", AsyncMock(return_value=mock_response)
        ):
            results = []
            async for page in client.send_paginated_request(
                "query", params={"__path": "organization.repositories"}
            ):
                results.append(page)

            assert len(results) == 0

    async def test_send_paginated_request_missing_path(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        client = GithubGraphQLClient(
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
        )

        with pytest.raises(
            GraphQLClientError, match="GraphQL pagination requires a '__path'"
        ):
            async for _ in client.send_paginated_request("query"):
                pass
