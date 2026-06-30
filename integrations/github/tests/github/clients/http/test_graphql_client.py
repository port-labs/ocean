import pytest
from typing import cast
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from github.clients.auth.abstract_authenticator import AbstractGitHubAuthenticator
from github.clients.auth.retry_transport import GitHubRetryTransport
from github.clients.http.graphql_client import GithubGraphQLClient, PAGE_SIZE
from github.helpers.exceptions import GraphQLClientError, GraphQLErrorGroup

_GQL_HOST = "https://api.github.com"
_GQL_ORG = "test-org"


def _make_gql_client(
    authenticator: AbstractGitHubAuthenticator,
) -> GithubGraphQLClient:
    return GithubGraphQLClient(
        organization=_GQL_ORG,
        github_host=_GQL_HOST,
        authenticator=authenticator,
    )


def _gateway_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", f"{_GQL_HOST}/graphql")
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError("server error", request=request, response=response)


class TestGithubGraphQLClient:
    def test_graphql_base_url_github_com(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        client = GithubGraphQLClient(
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
        )
        assert client.base_url == "https://api.github.com/graphql"

    def test_graphql_base_url_ghe_api_v3(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        client = GithubGraphQLClient(
            organization="test-org",
            github_host="https://ghe.example.com/api/v3",
            authenticator=authenticator,
        )
        assert client.base_url == "https://ghe.example.com/api/graphql"

    @pytest.mark.asyncio
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
        mock_response.headers = {}  # Add headers attribute
        mock_response.json.return_value = {
            "errors": [
                {"message": "Error 1", "path": ["field1"], "type": "CUSTOM_ERROR_1"},
                {"message": "Error 2", "path": ["field2"], "type": "CUSTOM_ERROR_2"},
            ]
        }

        # Mock the client's configuration
        mock_config = MagicMock()
        mock_config.client_timeout = 30.0  # Set a proper float value for timeout

        with patch(
            "port_ocean.helpers.async_client.OceanAsyncClient.request",
            AsyncMock(return_value=mock_response),
        ):
            with pytest.raises(GraphQLErrorGroup) as exc_info:
                await client.send_api_request(
                    client.base_url, method="POST", json_data={}
                )

            # Verify the exception group
            assert (
                str(exc_info.value) == "GraphQL errors occurred:\n- Error 1\n- Error 2"
            )
            assert len(exc_info.value.errors) == 2
            assert str(exc_info.value.errors[0]) == "Error 1"
            assert str(exc_info.value.errors[1]) == "Error 2"

    @pytest.mark.asyncio
    async def test_handle_graphql_success(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        client = GithubGraphQLClient(
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
        )

        # Mock successful response
        mock_response_data = {
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
            client, "send_api_request", AsyncMock(return_value=mock_response_data)
        ):
            response = await client.send_api_request(
                client.base_url, method="POST", json_data={}
            )
            assert response["data"]["organization"]["repositories"]["nodes"] == [
                {"id": 1, "name": "repo1"}
            ]

    @pytest.mark.asyncio
    async def test_send_paginated_request_single_page(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        client = GithubGraphQLClient(
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
        )

        # Mock response with no next page
        mock_response_data = {
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
            client, "send_api_request", AsyncMock(return_value=mock_response_data)
        ):
            results = []
            async for page in client.send_paginated_request(
                "query", params={"__path": "organization.repositories"}
            ):
                results.append(page)

            assert len(results) == 1
            assert results[0] == [{"id": 1, "name": "repo1"}]

    @pytest.mark.asyncio
    async def test_send_paginated_request_multiple_pages(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        client = GithubGraphQLClient(
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
        )

        # First response with next page

        first_response_data = {
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

        second_response_data = {
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
            AsyncMock(side_effect=[first_response_data, second_response_data]),
        ):
            results = []
            async for page in client.send_paginated_request(
                "query", params={"__path": "organization.repositories"}
            ):
                results.append(page)

            assert len(results) == 2
            assert results[0] == [{"id": 1, "name": "repo1"}]
            assert results[1] == [{"id": 2, "name": "repo2"}]

    @pytest.mark.asyncio
    async def test_send_paginated_request_resets_page_size_each_page(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        """Every page is built fresh at PAGE_SIZE — a reduced page size never persists.

        GitHubRetryTransport shrinks `variables.first` only within a single
        request's retry chain; the reduced request never flows back to the
        client. Because send_paginated_request rebuilds the payload from scratch
        on every iteration, each page returns to the full PAGE_SIZE regardless of
        how far a previous page was shrunk to recover from a 5xx.
        """
        client = GithubGraphQLClient(
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
        )

        first_response_data = {
            "data": {
                "organization": {
                    "repositories": {
                        "nodes": [{"id": 1, "name": "repo1"}],
                        "pageInfo": {"hasNextPage": True, "endCursor": "cursor1"},
                    }
                }
            }
        }
        second_response_data = {
            "data": {
                "organization": {
                    "repositories": {
                        "nodes": [{"id": 2, "name": "repo2"}],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            }
        }

        mock_send = AsyncMock(side_effect=[first_response_data, second_response_data])
        with patch.object(client, "send_api_request", mock_send):
            async for _ in client.send_paginated_request(
                "query", params={"__path": "organization.repositories"}
            ):
                pass

        page_sizes = [
            call.kwargs["json_data"]["variables"]["first"]
            for call in mock_send.call_args_list
        ]
        assert page_sizes == [PAGE_SIZE, PAGE_SIZE]

    @pytest.mark.asyncio
    async def test_send_paginated_request_empty_response(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        client = GithubGraphQLClient(
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
        )

        # Mock response with empty nodes
        mock_response_data = {
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
            client, "send_api_request", AsyncMock(return_value=mock_response_data)
        ):
            results = []
            async for page in client.send_paginated_request(
                "query", params={"__path": "organization.repositories"}
            ):
                results.append(page)

            assert len(results) == 0

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
    async def test_send_paginated_request_falls_back_on_gateway_error(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        client = _make_gql_client(authenticator)
        page: dict[str, object] = {
            "data": {
                "organization": {
                    "repositories": {
                        "nodes": [{"id": 1}],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            }
        }
        queries: list[str] = []

        async def fake_send(*_: object, **kwargs: object) -> dict[str, object]:
            payload = cast(dict[str, object], kwargs["json_data"])
            queries.append(cast(str, payload["query"]))
            if len(queries) == 1:
                raise _gateway_error(502)
            return page

        with patch.object(client, "send_api_request", new=fake_send):
            results = [
                p
                async for p in client.send_paginated_request(
                    "PRIMARY",
                    params={"__path": "organization.repositories"},
                    fallback_queries=["FALLBACK"],
                )
            ]

        assert results == [[{"id": 1}]]
        assert queries == ["PRIMARY", "FALLBACK"]

    @pytest.mark.asyncio
    async def test_fallback_query_persists_for_subsequent_pages(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        client = _make_gql_client(authenticator)
        page1: dict[str, object] = {
            "data": {
                "organization": {
                    "repositories": {
                        "nodes": [{"id": 1}],
                        "pageInfo": {"hasNextPage": True, "endCursor": "c1"},
                    }
                }
            }
        }
        page2: dict[str, object] = {
            "data": {
                "organization": {
                    "repositories": {
                        "nodes": [{"id": 2}],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            }
        }
        queries: list[str] = []
        cursors: list[object] = []

        async def fake_send(*_: object, **kwargs: object) -> dict[str, object]:
            payload = cast(dict[str, object], kwargs["json_data"])
            queries.append(cast(str, payload["query"]))
            variables = cast(dict[str, object], payload["variables"])
            cursors.append(variables.get("after"))
            if len(queries) == 1:
                raise _gateway_error(504)
            return page1 if len(queries) == 2 else page2

        with patch.object(client, "send_api_request", new=fake_send):
            results = [
                p
                async for p in client.send_paginated_request(
                    "PRIMARY",
                    params={"__path": "organization.repositories"},
                    fallback_queries=["FALLBACK"],
                )
            ]

        # Page that 504'd is retried at the same cursor with the lighter query,
        # and every later page keeps using it.
        assert results == [[{"id": 1}], [{"id": 2}]]
        assert queries == ["PRIMARY", "FALLBACK", "FALLBACK"]
        assert cursors == [None, None, "c1"]

    @pytest.mark.asyncio
    async def test_gateway_error_without_fallback_propagates(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        client = _make_gql_client(authenticator)
        with patch.object(
            client, "send_api_request", AsyncMock(side_effect=_gateway_error(502))
        ):
            with pytest.raises(httpx.HTTPStatusError):
                async for _ in client.send_paginated_request(
                    "PRIMARY", params={"__path": "organization.repositories"}
                ):
                    pass

    @pytest.mark.asyncio
    async def test_exhausted_fallbacks_propagate(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        client = _make_gql_client(authenticator)
        with patch.object(
            client, "send_api_request", AsyncMock(side_effect=_gateway_error(502))
        ):
            with pytest.raises(httpx.HTTPStatusError):
                async for _ in client.send_paginated_request(
                    "PRIMARY",
                    params={"__path": "organization.repositories"},
                    fallback_queries=["FALLBACK"],
                ):
                    pass

    @pytest.mark.asyncio
    async def test_non_gateway_status_not_retried_with_fallback(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        client = _make_gql_client(authenticator)
        with patch.object(
            client, "send_api_request", AsyncMock(side_effect=_gateway_error(400))
        ):
            with pytest.raises(httpx.HTTPStatusError):
                async for _ in client.send_paginated_request(
                    "PRIMARY",
                    params={"__path": "organization.repositories"},
                    fallback_queries=["FALLBACK"],
                ):
                    pass

    def test_is_query_too_expensive_keys_on_gateway_status(self) -> None:
        for status in (500, 502, 504, 499):
            assert GithubGraphQLClient._is_query_too_expensive(_gateway_error(status))
        for status in (400, 403, 404):
            assert not GithubGraphQLClient._is_query_too_expensive(
                _gateway_error(status)
            )
        assert not GithubGraphQLClient._is_query_too_expensive(GraphQLErrorGroup([]))


class TestGithubGraphQLClientRetryConfig:
    """Tests for client property override — POST retryability and caching."""

    def test_graphql_client_transport_has_post_retryable(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        gql_client = _make_gql_client(authenticator)

        with patch("github.clients.auth.abstract_authenticator.ocean") as mock_ocean:
            mock_ocean.config.client_timeout = 60
            transport = cast(GitHubRetryTransport, gql_client.client._transport)
            retryable = transport._retry_config.retryable_methods

        assert "POST" in retryable

    def test_rest_client_transport_does_not_have_post_retryable(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        with patch("github.clients.auth.abstract_authenticator.ocean") as mock_ocean:
            mock_ocean.config.client_timeout = 60
            transport = cast(GitHubRetryTransport, authenticator.client._transport)
            retryable = transport._retry_config.retryable_methods

        assert "POST" not in retryable

    def test_client_is_cached_per_instance(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        gql_client = _make_gql_client(authenticator)

        with patch("github.clients.auth.abstract_authenticator.ocean") as mock_ocean:
            mock_ocean.config.client_timeout = 60
            first = gql_client.client
            second = gql_client.client

        assert first is second

    def test_client_is_separate_from_authenticator_default_client(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        gql_client = _make_gql_client(authenticator)

        with patch("github.clients.auth.abstract_authenticator.ocean") as mock_ocean:
            mock_ocean.config.client_timeout = 60
            assert gql_client.client is not authenticator.client

    def test_different_graphql_instances_have_independent_client_caches(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        gql1 = _make_gql_client(authenticator)
        gql2 = _make_gql_client(authenticator)

        with patch("github.clients.auth.abstract_authenticator.ocean") as mock_ocean:
            mock_ocean.config.client_timeout = 60
            assert gql1.client is not gql2.client

    @pytest.mark.asyncio
    async def test_graphql_client_retries_post_on_transient_error(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        gql_client = _make_gql_client(authenticator)
        calls: list[int] = []

        async def fake_handle(
            self: httpx.AsyncHTTPTransport, request: httpx.Request
        ) -> httpx.Response:
            calls.append(1)
            headers = {"Content-Length": "0"}
            if len(calls) == 1:
                return httpx.Response(502, headers=headers, request=request)
            return httpx.Response(200, headers=headers, request=request)

        with (
            patch("github.clients.auth.abstract_authenticator.ocean") as mock_ocean,
            patch.object(httpx.AsyncHTTPTransport, "handle_async_request", fake_handle),
            patch("port_ocean.helpers.retry.asyncio.sleep", new=AsyncMock()),
            patch.object(
                authenticator,
                "get_headers",
                AsyncMock(
                    return_value=AsyncMock(
                        as_dict=lambda: {"Authorization": "Bearer test"}
                    )
                ),
            ),
        ):
            mock_ocean.config.client_timeout = 60
            client = gql_client.client
            resp = await client.post(f"{_GQL_HOST}/graphql", json={})
            await client.aclose()

        assert resp.status_code == 200
        assert len(calls) == 2
