from typing import Any, AsyncGenerator, Dict, List, Optional
from urllib.parse import urljoin

from loguru import logger
from httpx import Response

from github.clients.http.base_client import AbstractGithubClient
from github.helpers.exceptions import GraphQLClientError

PAGE_SIZE = 25


class GithubGraphQLClient(AbstractGithubClient):
    """GraphQL API implementation of GitHub client."""

    @property
    def base_url(self) -> str:
        return urljoin(self.github_host, "/graphql")

    def _handle_graphql_errors(self, response: Response) -> None:
        result = response.json()
        if "errors" in result:
            errors = result["errors"]
            exceptions = [GraphQLClientError(error) for error in errors]
            raise ExceptionGroup("GraphQL errors occurred.", exceptions)

    async def send_api_request(
        self,
        resource: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "POST",
        json_data: Optional[Dict[str, Any]] = None,
        return_full_response: bool = True,
    ) -> Any:
        response = await super().send_api_request(
            resource=resource,
            params=params,
            method=method,
            json_data=json_data,
            return_full_response=return_full_response,
        )
        self._handle_graphql_errors(response)
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
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        params = params or {}
        path = params.pop("__path", None)
        if not path:
            raise GraphQLClientError(
                "GraphQL pagination requires a '__path' in params (e.g., 'organization.repositories')"
            )

        cursor = None
        logger.info(f"Starting GraphQL pagination for query with path {path}")

        while True:
            payload = self.build_graphql_payload(resource, params, cursor=cursor)
            response = await self.send_api_request(
                self.base_url, method=method, json_data=payload
            )
            data = response.json()["data"]
            nodes = self._extract_nodes(data, path)
            if not nodes:
                return

            yield nodes
            page_info = self._extract_page_info(data, path)
            if not page_info or not page_info.get("hasNextPage"):
                break

            cursor = page_info.get("endCursor")
            logger.debug(f"Next page cursor: {cursor}")

    def _extract_nodes(self, data: Dict[str, Any], path: str) -> List[Dict[str, Any]]:
        keys = path.split(".")
        current = data
        for key in keys:
            current = current[key]
        return current["nodes"]

    def _extract_page_info(self, data: Dict[str, Any], path: str) -> Dict[str, Any]:
        keys = path.split(".")
        current = data
        for key in keys:
            current = current[key]
        return current["pageInfo"]
