from typing import Any, AsyncIterator, Optional

from loguru import logger

from gitlab.clients.base_client import HTTPBaseClient
from gitlab.clients.queries.group_vulnerabilities import VULNERABILITIES_QUERY


class GraphQLClient(HTTPBaseClient):
    DEFAULT_PAGE_SIZE = 100
    RESOURCE_QUERIES = {
        "vulnerabilities": VULNERABILITIES_QUERY,
    }

    async def get_paginated_group_resource(
        self,
        group_path: str,
        resource_type: str,
        params: Optional[dict[str, Any]] = None,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        logger.info(
            f"Fetching {resource_type} for group {group_path} with params: {params}"
        )
        async for batch in self._make_paginated_request(
            group_path, resource_type, params
        ):
            if batch:
                logger.info(
                    f"Received batch of {len(batch)} {resource_type} for group {group_path}"
                )
                yield batch

    async def _make_paginated_request(
        self,
        group_path: str,
        resource_type: str,
        params: Optional[dict[str, Any]] = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        query = self.RESOURCE_QUERIES[resource_type]
        variables = {"groupPath": group_path, "first": page_size}
        if params:
            variables.update(params)

        page = 1
        after = None

        while True:
            if after:
                variables["after"] = after

            logger.debug(f"Fetching page {page} for group {group_path} {resource_type}")
            response = await self.send_api_request(
                "POST", "", data={"query": query, "variables": variables}
            )

            data = response["data"]
            group_data = data["group"]
            resource_data = group_data[resource_type]

            batch = resource_data["nodes"]
            page_info = resource_data["pageInfo"]

            if not batch:
                logger.debug(f"No more {resource_type} for group {group_path}")
                break

            yield batch

            if not page_info["hasNextPage"]:
                logger.debug(
                    f"Last page reached for group {group_path} {resource_type}"
                )
                break

            after = page_info["endCursor"]
            page += 1
