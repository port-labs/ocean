import pytest
from typing import cast, List, Optional
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from github.clients.auth.abstract_authenticator import AbstractGitHubAuthenticator
from github.clients.auth.retry_transport import (
    GitHubRetryTransport,
    MIN_GRAPHQL_PAGE_SIZE,
)
from github.clients.http.graphql_client import GithubGraphQLClient, PAGE_SIZE
from github.helpers.exceptions import GraphQLClientError, GraphQLErrorGroup
from github.helpers.utils import IgnoredError
from github.helpers.exceptions import (
    GraphQLClientError,
    GraphQLErrorGroup,
    RateLimitException,
)

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
        mock_response.extensions = {}  # Carries the transport's sent variables
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
    async def test_fallback_is_scoped_per_page_and_resets_to_primary(
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
        firsts: list[object] = []

        async def fake_send(*_: object, **kwargs: object) -> dict[str, object]:
            payload = cast(dict[str, object], kwargs["json_data"])
            queries.append(cast(str, payload["query"]))
            variables = cast(dict[str, object], payload["variables"])
            cursors.append(variables.get("after"))
            firsts.append(variables.get("first"))
            # Only the first page's primary attempt is too expensive.
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

        assert results == [[{"id": 1}], [{"id": 2}]]
        # Page 1 escalates to the lighter query at the floor; page 2 starts over
        # at the full query and page size — the escalation does not persist.
        assert queries == ["PRIMARY", "FALLBACK", "PRIMARY"]
        assert cursors == [None, None, "c1"]
        assert firsts == [PAGE_SIZE, MIN_GRAPHQL_PAGE_SIZE, PAGE_SIZE]

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
        # Gateway timeouts signal an over-budget query and trigger the fallback.
        for status in (502, 504, 499):
            assert GithubGraphQLClient._is_query_too_expensive(_gateway_error(status))
        # A plain 500 is a generic server error, not an over-budget signal, so it
        # gets page-size backoff but never the field-stripping query fallback.
        assert not GithubGraphQLClient._is_query_too_expensive(_gateway_error(500))
        for status in (400, 403, 404):
            assert not GithubGraphQLClient._is_query_too_expensive(
                _gateway_error(status)
            )
        assert not GithubGraphQLClient._is_query_too_expensive(GraphQLErrorGroup([]))

    @pytest.mark.asyncio
    async def test_handle_graphql_errors_detects_rate_limit_response(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        """Test that _handle_graphql_errors raises RateLimitException for rate-limited responses."""
        client = GithubGraphQLClient(
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
        )

        # Mock rate-limit response (HTTP 200 with exhausted headers)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = {
            "x-ratelimit-limit": "5000",
            "x-ratelimit-remaining": "0",
            "x-ratelimit-reset": "1700000000",
        }
        mock_response.extensions = {}

        with pytest.raises(RateLimitException) as exc_info:
            client._handle_graphql_errors(mock_response)

        assert exc_info.value.rate_limit_info.limit == 5000
        assert exc_info.value.rate_limit_info.remaining == 0
        assert exc_info.value.rate_limit_info.reset_time == 1700000000

    @pytest.mark.asyncio
    async def test_send_api_request_retries_on_rate_limit(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        """Test that send_api_request retries after catching RateLimitException."""
        client = GithubGraphQLClient(
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
        )

        # First response: rate-limited
        rate_limit_response = MagicMock(spec=httpx.Response)
        rate_limit_response.status_code = 200
        rate_limit_response.headers = {
            "x-ratelimit-limit": "5000",
            "x-ratelimit-remaining": "0",
            "x-ratelimit-reset": "1700000000",
        }
        rate_limit_response.extensions = {}

        # Second response: success
        success_response = MagicMock(spec=httpx.Response)
        success_response.status_code = 200
        success_response.headers = {}
        success_response.extensions = {}
        success_response.json.return_value = {
            "data": {"organization": {"repositories": {"nodes": []}}}
        }

        make_request_mock = AsyncMock(
            side_effect=[rate_limit_response, success_response]
        )

        with patch.object(client, "make_request", make_request_mock):
            with patch("asyncio.sleep", new_callable=AsyncMock) as sleep_mock:
                result = await client.send_api_request(
                    client.base_url, method="POST", json_data={}
                )

                # Verify retry happened
                assert make_request_mock.call_count == 2
                # Verify sleep was called with the correct duration
                sleep_mock.assert_called_once()
                sleep_duration = sleep_mock.call_args[0][0]
                # Sleep duration should be non-negative (reset_time - current_time)
                assert sleep_duration >= 0
                # Verify the result is from the successful response
                assert result == {
                    "data": {"organization": {"repositories": {"nodes": []}}}
                }

    @pytest.mark.asyncio
    async def test_send_api_request_rate_limit_logs_warning(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        """Test that rate-limit retry logs a warning message."""
        client = GithubGraphQLClient(
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
        )

        # First response: rate-limited
        rate_limit_response = MagicMock(spec=httpx.Response)
        rate_limit_response.status_code = 200
        rate_limit_response.headers = {
            "x-ratelimit-limit": "5000",
            "x-ratelimit-remaining": "0",
            "x-ratelimit-reset": "1700000000",
        }
        rate_limit_response.extensions = {}

        # Second response: success
        success_response = MagicMock(spec=httpx.Response)
        success_response.status_code = 200
        success_response.headers = {}
        success_response.extensions = {}
        success_response.json.return_value = {"data": {}}

        make_request_mock = AsyncMock(
            side_effect=[rate_limit_response, success_response]
        )

        with patch.object(client, "make_request", make_request_mock):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                with patch("github.clients.http.graphql_client.logger") as logger_mock:
                    await client.send_api_request(
                        client.base_url,
                        method="POST",
                        json_data={},
                        query_path="test.query",
                    )

                    # Verify warning was logged
                    logger_mock.warning.assert_called_once()
                    warning_msg = logger_mock.warning.call_args[0][0]
                    assert "Rate limit exceeded" in warning_msg
                    assert "test.query" in warning_msg

    @pytest.mark.asyncio
    async def test_send_api_request_bounded_retry_loop(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        """Test that send_api_request retries max 5 times on rate limit before raising."""
        client = GithubGraphQLClient(
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
        )

        # Always return rate-limited response
        rate_limit_response = MagicMock(spec=httpx.Response)
        rate_limit_response.status_code = 200
        rate_limit_response.headers = {
            "x-ratelimit-limit": "5000",
            "x-ratelimit-remaining": "0",
            "x-ratelimit-reset": "1700000000",
        }
        rate_limit_response.extensions = {}

        make_request_mock = AsyncMock(return_value=rate_limit_response)

        with patch.object(client, "make_request", make_request_mock):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(RateLimitException):
                    await client.send_api_request(
                        client.base_url,
                        method="POST",
                        json_data={},
                        query_path="test.query",
                    )

                # Verify make_request was called 5 times (max retries)
                assert make_request_mock.call_count == 5


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


class TestGraphQLUnknownErrorPageReduction:
    """A page whose 200 body carries unknown (non-ignored) errors shrinks `first` and retries."""

    _PATH = "organization.repositories"

    def _error_body(self, message: str = "boom") -> dict:
        return {"errors": [{"message": message, "type": "UNKNOWN"}]}

    def _page_body(
        self, nodes: list, has_next: bool = False, cursor: object = None
    ) -> dict:
        return {
            "data": {
                "organization": {
                    "repositories": {
                        "nodes": nodes,
                        "pageInfo": {"hasNextPage": has_next, "endCursor": cursor},
                    }
                }
            }
        }

    async def _collect(
        self,
        client: GithubGraphQLClient,
        ignored_errors: Optional[List[IgnoredError]] = None,
    ) -> list:
        return [
            page
            async for page in client.send_paginated_request(
                "query",
                params={"__path": self._PATH},
                ignored_errors=ignored_errors,
            )
        ]

    @pytest.mark.asyncio
    async def test_reduces_page_size_and_recovers(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        client = _make_gql_client(authenticator)
        seen_first = []

        async def fake_make_request(**kwargs: object) -> httpx.Response:
            first = cast(dict, kwargs["json_data"])["variables"]["first"]
            seen_first.append(first)
            if first == PAGE_SIZE:
                return httpx.Response(200, json=self._error_body())
            return httpx.Response(200, json=self._page_body([{"id": 1}]))

        with patch.object(client, "make_request", side_effect=fake_make_request):
            pages = await self._collect(client)

        assert pages == [[{"id": 1}]]
        assert seen_first == [PAGE_SIZE, PAGE_SIZE - 5]

    @pytest.mark.asyncio
    async def test_walks_down_to_floor_then_raises(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        client = _make_gql_client(authenticator)
        seen_first = []

        async def fake_make_request(**kwargs: object) -> httpx.Response:
            seen_first.append(cast(dict, kwargs["json_data"])["variables"]["first"])
            return httpx.Response(200, json=self._error_body())

        with patch.object(client, "make_request", side_effect=fake_make_request):
            with pytest.raises(GraphQLErrorGroup):
                await self._collect(client)

        assert seen_first == [25, 20, 15, 10, 5, 1]

    @pytest.mark.asyncio
    async def test_page_size_resets_to_full_on_next_page(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        client = _make_gql_client(authenticator)
        seen_first = []

        async def fake_make_request(**kwargs: object) -> httpx.Response:
            seen_first.append(cast(dict, kwargs["json_data"])["variables"]["first"])
            if len(seen_first) == 1:
                return httpx.Response(200, json=self._error_body())
            if len(seen_first) == 2:
                return httpx.Response(
                    200, json=self._page_body([{"id": 1}], has_next=True, cursor="c1")
                )
            return httpx.Response(200, json=self._page_body([{"id": 2}]))

        with patch.object(client, "make_request", side_effect=fake_make_request):
            pages = await self._collect(client)

        assert pages == [[{"id": 1}], [{"id": 2}]]
        # 25 fails, 20 succeeds for page 1, then page 2 starts fresh at 25.
        assert seen_first == [25, 20, 25]

    @pytest.mark.asyncio
    async def test_ignored_errors_do_not_trigger_reduction(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        client = _make_gql_client(authenticator)
        ignored_body = {
            "errors": [{"message": "quota", "type": "IGNORED", "path": ["x"]}]
        }
        make_request = AsyncMock(return_value=httpx.Response(200, json=ignored_body))

        with patch.object(client, "make_request", make_request):
            pages = await self._collect(
                client, ignored_errors=[IgnoredError(status=200, type="IGNORED")]
            )

        assert pages == []
        make_request.assert_awaited_once()
