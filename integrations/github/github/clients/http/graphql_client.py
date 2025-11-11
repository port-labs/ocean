from typing import Any, AsyncGenerator, Dict, List, Optional

from loguru import logger

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

    def _compute_graphql_base_url(self, github_host: str) -> str:
        parsed = urlparse(github_host.rstrip("/"))
        graphql_path = "/api/graphql" if parsed.path.startswith("/api/") else "/graphql"
        return urlunparse(
            parsed._replace(path=graphql_path, params="", query="", fragment="")
        )

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
        response: Dict[str, Any],
        ignored_errors: Optional[List[IgnoredError]] = None,
    ) -> Dict[str, Any]:
        if "errors" not in response:
            return response

        ignored_errors = ignored_errors or []
        ignored_errors.extend(self._DEFAULT_IGNORED_ERRORS)
        ignored_types = {e.type: e.message for e in ignored_errors}

        non_ignored_exceptions = []

        for error in response["errors"]:
            error_type = error.get("type")
            if error_type in ignored_types:
                log_message = f"{ignored_types[error_type]} due to {error['message']} for {error.get('path', [])})"
                logger.warning(log_message)
                continue
            non_ignored_exceptions.append(GraphQLClientError(error["message"]))

        if non_ignored_exceptions:
            raise GraphQLErrorGroup(non_ignored_exceptions)

        return {}

    async def send_api_request(
        self,
        resource: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "POST",
        json_data: Optional[Dict[str, Any]] = None,
        ignored_errors: Optional[List[IgnoredError]] = None,
        ignore_default_errors: bool = True,
    ) -> Dict[str, Any]:
        response = await super().send_api_request(
            resource=resource,
            params=params,
            method=method,
            json_data=json_data,
            ignored_errors=ignored_errors,
        )
        response = self._handle_graphql_errors(response, ignored_errors)
        return response

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
        logger.info(f"Starting GraphQL pagination for query with path {path}")

        while True:
            payload = self.build_graphql_payload(resource, params, cursor=cursor)
            response = await self.send_api_request(
                self.base_url,
                method=method,
                json_data=payload,
                ignored_errors=ignored_errors,
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
            logger.debug(f"Next page cursor: {cursor}")

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
