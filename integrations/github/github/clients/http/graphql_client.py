from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from loguru import logger

from github.clients.constants import GRAPHQL_SENT_VARIABLES_EXTENSION
from github.clients.graphql_page_reduction import reduce_graphql_page_size
from github.clients.http.base_client import AbstractGithubClient
from github.helpers.exceptions import GraphQLClientError, GraphQLErrorGroup
from github.helpers.utils import IgnoredError
from github.clients.rate_limiter.utils import GitHubRateLimiterConfig
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
            self._graphql_client = self.authenticator._make_client(frozenset({"POST"}))
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

    def _non_ignored_errors(
        self,
        body: Dict[str, Any],
        ignored_errors: Optional[List[IgnoredError]],
        status_code: int,
    ) -> List[GraphQLClientError]:
        """Non-ignored errors in a GraphQL body, logging and dropping ignored ones."""
        if "errors" not in body:
            return []

        all_ignored = [*(ignored_errors or []), *self._DEFAULT_IGNORED_ERRORS]
        ignored_types = {e.type: e.message for e in all_ignored}

        non_ignored_exceptions = []
        for error in body["errors"]:
            error_type = error.get("type")
            if error_type in ignored_types:
                logger.warning(
                    f"{ignored_types[error_type]} due to {error['message']} "
                    f"for {error.get('path', [])} (status {status_code})"
                )
                continue
            non_ignored_exceptions.append(GraphQLClientError(error["message"]))
        return non_ignored_exceptions

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
        response = await self.make_request(
            resource=resource,
            params=params,
            method=method,
            json_data=json_data,
            ignored_errors=ignored_errors,
            ignore_default_errors=ignore_default_errors,
            authenticator_headers_params=authenticator_headers_params,
        )
        body = response.json()
        errors = self._non_ignored_errors(body, ignored_errors, response.status_code)

        if errors:
            variables = (
                self._sent_variables(response)
                or (json_data or {}).get("variables")
                or query_params
            )
            logger.error(
                f"[GraphQL] Query failed with status {response.status_code} for "
                f"path {query_path} with variables {variables}"
            )
            raise GraphQLErrorGroup(errors)

        return {} if "errors" in body else body

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

    async def send_paginated_request(
        self,
        resource: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "POST",
        ignored_errors: Optional[List[IgnoredError]] = None,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        params = params or {}
        path = params.pop("__path", None)
        node_key = params.pop("__node_key", "nodes")
        if not path:
            raise GraphQLClientError(
                "GraphQL pagination requires a '__path' in params (e.g., 'organization.repositories')"
            )

        cursor = None
        page_size = PAGE_SIZE
        logger.info(f"[GraphQL] Starting pagination for query with path {path}")

        while True:
            payload = self.build_graphql_payload(
                resource, params, page_size=page_size, cursor=cursor
            )
            try:
                response = await self.send_api_request(
                    self.base_url,
                    method=method,
                    json_data=payload,
                    ignored_errors=ignored_errors,
                    query_path=path,
                    query_params=params,
                )
            except GraphQLErrorGroup:
                reduced_page_size = reduce_graphql_page_size(page_size)
                if reduced_page_size is None:
                    raise
                logger.warning(
                    f"[GraphQL] Query for path {path} failed at first={page_size}; "
                    f"retrying at first={reduced_page_size}"
                )
                page_size = reduced_page_size
                continue

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
            page_size = PAGE_SIZE
            logger.debug(f"[GraphQL] Next page cursor: {cursor}")

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
