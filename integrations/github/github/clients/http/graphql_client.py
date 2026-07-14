import asyncio
from http import HTTPStatus
from json import JSONDecodeError
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from loguru import logger

from github.clients.auth.retry_transport import (
    GATEWAY_TIMEOUT_STATUS_CODES,
    MIN_GRAPHQL_PAGE_SIZE,
)
from github.clients.constants import GRAPHQL_SENT_VARIABLES_EXTENSION
from github.clients.http.base_client import AbstractGithubClient
from github.helpers.exceptions import (
    GraphQLClientError,
    GraphQLErrorGroup,
    RateLimitException,
)
from github.helpers.utils import IgnoredError
from github.clients.rate_limiter.utils import (
    GitHubRateLimiterConfig,
    extract_graphql_rate_limit_info,
)
from urllib.parse import urlparse, urlunparse

PAGE_SIZE = 25


class GithubGraphQLClient(AbstractGithubClient):
    """GraphQL API implementation of GitHub client."""

    def __init__(
        self,
        github_host: str,
        authenticator: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(github_host=github_host, authenticator=authenticator, **kwargs)
        self._graphql_url = self._compute_graphql_base_url(self.github_host)
        self._graphql_client: Optional[httpx.AsyncClient] = None

    def _compute_graphql_base_url(self, github_host: str) -> str:
        parsed = urlparse(github_host.rstrip("/"))
        graphql_path = "/api/graphql" if parsed.path.startswith("/api/") else "/graphql"
        return urlunparse(
            parsed._replace(path=graphql_path, params="", query="", fragment="")
        )

    @property
    def client(self) -> httpx.AsyncClient:
        if self._graphql_client is None:
            self._graphql_client = self.authenticator._make_client(
                extra_retryable_methods=frozenset({"POST"}),
                extra_retryable_status=frozenset({HTTPStatus.FORBIDDEN}),
            )
        return self._graphql_client

    @property
    def base_url(self) -> str:
        return self._graphql_url

    @property
    def rate_limiter_config(self) -> GitHubRateLimiterConfig:
        return GitHubRateLimiterConfig(
            api_type="graphql",
            max_concurrent=5,
        )

    def _handle_graphql_errors(
        self,
        response: httpx.Response,
        ignored_errors: Optional[List[IgnoredError]] = None,
        query_path: Optional[str] = None,
        query_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        rate_limit_info = extract_graphql_rate_limit_info(response)
        if rate_limit_info is not None:
            raise RateLimitException(rate_limit_info)

        try:
            body = response.json()
        except JSONDecodeError:
            # Empty/non-JSON 2xx response; treat as no data instead of failing
            logger.warning(
                f"[GraphQL] Empty or non-JSON response body (status "
                f"{response.status_code}) for path {query_path}; treating as no data"
            )
            return {}

        if "errors" not in body:
            return body

        ignored_errors = ignored_errors or []
        ignored_errors.extend(self._DEFAULT_IGNORED_ERRORS)
        ignored_types = {e.type: e.message for e in ignored_errors}

        status_code = response.status_code
        non_ignored_exceptions = []

        for error in body["errors"]:
            error_type = error.get("type")
            if error_type in ignored_types:
                log_message = f"{ignored_types[error_type]} due to {error['message']} for {error.get('path', [])} (status {status_code})"
                logger.warning(log_message)
                continue
            non_ignored_exceptions.append(GraphQLClientError(error["message"]))

        if non_ignored_exceptions:
            # The transport can rewrite variables between retries (e.g. shrinking
            # `variables.first`); prefer what it actually sent over the caller's copy.
            variables = self._sent_variables(response) or query_params
            logger.error(
                f"[GraphQL] Query failed with status {status_code} for path "
                f"{query_path} with variables {variables}"
            )
            raise GraphQLErrorGroup(non_ignored_exceptions)

        return {}

    @staticmethod
    def _sent_variables(response: httpx.Response) -> Optional[Dict[str, Any]]:
        """Variables from the request that actually produced this response.

        The retry transport can rewrite a GraphQL request body between attempts
        (e.g. shrinking `variables.first` on a retryable 5xx), and httpx resets
        `response.request` to the caller's original request once the transport
        returns — so the transport records the variables it truly sent in the
        response extensions, which is what we read here for error logs.
        """
        return response.extensions.get(GRAPHQL_SENT_VARIABLES_EXTENSION)

    async def send_api_request(
        self,
        resource: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "POST",
        json_data: Optional[Dict[str, Any]] = None,
        ignored_errors: Optional[List[IgnoredError]] = None,
        ignore_default_errors: bool = True,
        authenticator_headers_params: Optional[Dict[str, Any]] = {},
        query_path: Optional[str] = None,
        query_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        while True:
            response = await self.make_request(
                resource=resource,
                params=params,
                method=method,
                json_data=json_data,
                ignored_errors=ignored_errors,
                ignore_default_errors=ignore_default_errors,
                authenticator_headers_params=authenticator_headers_params,
            )
            try:
                return self._handle_graphql_errors(
                    response,
                    ignored_errors,
                    query_path=query_path,
                    query_params=query_params,
                )
            except RateLimitException as exc:
                sleep_time = exc.rate_limit_info.seconds_until_reset
                logger.warning(
                    f"[GraphQL] Rate limit exceeded for path {query_path}. "
                    f"Sleeping for {sleep_time} seconds until {exc.rate_limit_info.reset_time}"
                )
                await asyncio.sleep(sleep_time)

    def build_graphql_payload(
        self,
        query: str,
        variables: Dict[str, Any],
        page_size: int = PAGE_SIZE,
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build a GraphQL payload with query and variables."""

        variables["first"] = page_size
        if cursor:
            variables["after"] = cursor
        return {"query": query, "variables": variables}

    @staticmethod
    def _is_query_too_expensive(exc: BaseException) -> bool:
        """True for a gateway timeout left over once the transport gives up.

        GitHub surfaces a query that blows the 10s GraphQL execution budget as a
        502/504 (and occasionally a 499 from its reverse proxy) — see
        GATEWAY_TIMEOUT_STATUS_CODES. The retry transport shrinks the page size on
        each of these and re-raises once it bottoms out at the floor, so by the
        time the error reaches here the page is already as small as it gets — the
        only lever left is a lighter query. A plain 500 is intentionally excluded:
        it's a generic server error, not an over-budget signal, so it should not
        trigger the field-stripping fallback.
        """
        return (
            isinstance(exc, httpx.HTTPStatusError)
            and exc.response.status_code in GATEWAY_TIMEOUT_STATUS_CODES
        )

    async def send_paginated_request(
        self,
        resource: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "POST",
        ignored_errors: Optional[List[IgnoredError]] = None,
        fallback_queries: Optional[List[str]] = None,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        params = params or {}
        path = params.pop("__path", None)
        node_key = params.pop("__node_key", "nodes")
        if not path:
            raise GraphQLClientError(
                "GraphQL pagination requires a '__path' in params (e.g., 'organization.repositories')"
            )

        fallbacks = list(fallback_queries or [])
        cursor = None
        logger.info(f"[GraphQL] Starting pagination for query with path {path}")

        while True:
            response = await self._fetch_page(
                resource,
                params,
                path=path,
                method=method,
                ignored_errors=ignored_errors,
                cursor=cursor,
                fallbacks=fallbacks,
            )
            if not response:
                break

            data = response["data"]
            nodes = self._extract_nodes(data, path, node_key)
            if not nodes:
                return

            yield nodes
            page_info = self._extract_page_info(data, path)
            if not page_info or not page_info.get("hasNextPage"):
                break

            cursor = page_info.get("endCursor")
            logger.debug(f"[GraphQL] Next page cursor: {cursor}")

    async def _fetch_page(
        self,
        query: str,
        params: Dict[str, Any],
        path: str,
        method: str,
        ignored_errors: Optional[List[IgnoredError]],
        cursor: Optional[str],
        fallbacks: List[str],
    ) -> Dict[str, Any]:
        """Fetch a single page, escalating to lighter queries only for this page.

        Every page starts fresh at the full query and PAGE_SIZE. The retry
        transport shrinks the page size on a gateway 5xx; only if the query still
        fails once it bottoms out at the floor do we strip to a lighter fallback
        query — run at the floor, since the full page already proved too heavy.
        The escalation is scoped to this page: the next cursor starts over at the
        full query and page size, so a single expensive page never degrades the
        rest of the pagination.
        """
        attempts = [(query, PAGE_SIZE)] + [
            (fallback, MIN_GRAPHQL_PAGE_SIZE) for fallback in fallbacks
        ]
        for index, (attempt_query, page_size) in enumerate(attempts):
            payload = self.build_graphql_payload(
                attempt_query, params, page_size=page_size, cursor=cursor
            )
            try:
                return await self.send_api_request(
                    self.base_url,
                    method=method,
                    json_data=payload,
                    ignored_errors=ignored_errors,
                    query_path=path,
                    query_params=params,
                )
            except httpx.HTTPStatusError as exc:
                is_last_attempt = index == len(attempts) - 1
                if is_last_attempt or not self._is_query_too_expensive(exc):
                    raise
                logger.warning(
                    f"[GraphQL] Query for path {path} exceeded GitHub's execution "
                    f"budget at the smallest page size; retrying this page with a "
                    f"lighter query at first={MIN_GRAPHQL_PAGE_SIZE} "
                    f"({len(attempts) - index - 1} fallback(s) remaining)"
                )
        raise AssertionError("unreachable: attempts always includes the primary query")

    def _extract_nodes(
        self, data: Dict[str, Any], path: str, node_key: str = "nodes"
    ) -> List[Dict[str, Any]]:
        keys = path.split(".")
        current: dict[str, Any] = data
        for key in keys:
            current = current[key]
        return current[node_key]

    def _extract_page_info(self, data: Dict[str, Any], path: str) -> Dict[str, Any]:
        keys = path.split(".")
        current = data
        for key in keys:
            current = current[key]

        return current["pageInfo"]
