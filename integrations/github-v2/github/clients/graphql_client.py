from typing import Any, AsyncGenerator, Awaitable, Callable, Dict, List, Optional
from urllib.parse import urljoin

from github.clients.base_client import AbstractGithubClient
from loguru import logger
from httpx import Response


PAGE_SIZE = 25


class GithubGraphQLClient(AbstractGithubClient):
    """GraphQL API implementation of GitHub client."""

    @property
    def base_url(self) -> str:
        return urljoin(self.github_host, "/graphql")

    async def _handle_graphql_errors(self, response: Response) -> None:
        result = response.json()
        if "errors" in result:
            logger.error(f"GraphQL query errors: {result['errors']}")
            raise Exception(f"GraphQL query failed: {result['errors']}")

    async def send_api_request(
        self,
        resource: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET",
        json_data: Optional[Dict[str, Any]] = None,
        error_handler: Optional[Callable[[Response], Awaitable[None]]] = None,
    ) -> Response:
        return await super().send_api_request(
            resource=resource,
            params=params,
            method=method,
            json_data=json_data,
            error_handler=self._handle_graphql_errors,
        )

    def build_graphql_payload(
        self,
        query: str,
        variables: Dict[str, Any],
        page_size: int = PAGE_SIZE,
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build a GraphQL payload with query and variables."""
        vars = variables.copy()
        vars["first"] = page_size
        if cursor:
            vars["after"] = cursor
        return {"query": query, "variables": vars}

    async def send_paginated_request(
        self,
        resource: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "POST",
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        params = params or {}
        path = params.pop("__path", None)
        if not path:
            raise ValueError(
                "GraphQL pagination requires a '__path' in params (e.g., 'organization.repositories')"
            )

        cursor = None
        logger.info(f"Starting GraphQL pagination for query with path {path}")

        while True:
            payload = self.build_graphql_payload(resource, params, cursor=cursor)
            response = await self.send_api_request(
                self.base_url, method="POST", json_data=payload
            )
            data = response.json()["data"]
            nodes = self._extract_nodes(data, path)
            if not nodes:
                return
            yield nodes
            page_info = self._extract_page_info(data, path)
            if not page_info or not page_info.get("hasNextPage"):
                return
            cursor = page_info.get("endCursor")
            logger.debug(f"Next page cursor: {cursor}")

    def _extract_nodes(self, data: Dict[str, Any], path: str) -> List[Dict[str, Any]]:
        keys = path.split(".")
        current = data
        for key in keys:
            current = current.get(key, {})
            if not isinstance(current, dict):
                logger.error(f"Invalid path '{path}' at key '{key}': {current}")
                return []
        return current.get("nodes", []) if isinstance(current, dict) else []

    def _extract_page_info(
        self, data: Dict[str, Any], path: str
    ) -> Optional[Dict[str, Any]]:
        keys = path.split(".")
        current = data
        for key in keys:
            current = current.get(key, {})
            if not isinstance(current, dict):
                logger.error(
                    f"Invalid pageInfo path '{path}' at key '{key}': {current}"
                )
                return None
        return current.get("pageInfo") if isinstance(current, dict) else None
