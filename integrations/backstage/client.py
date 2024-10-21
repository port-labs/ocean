from typing import Any, List, Optional

from loguru import logger

from port_ocean.utils import http_async_client

PAGE_SIZE = 20


class BackstageClient:
    BASE_ENDPOINT = "api/catalog/entities/by-query"

    def __init__(self, backstage_host: str, backstage_token: str) -> None:
        logger.info(f"Initializing BackstageClient with host: {backstage_host}")
        self.backstage_host = backstage_host
        self.backstage_token = backstage_token

        self.client = http_async_client
        self.api_auth_header = {"Authorization": f"Bearer {self.backstage_token}"}
        self.client.headers.update(self.api_auth_header)

    @property
    def entities_query_endpoint(self) -> str:
        return f"{self.backstage_host}/{BackstageClient.BASE_ENDPOINT}"

    def _add_identifier(self, entity: Any) -> Any:
        name = entity["metadata"]["name"]
        namespace = entity["metadata"]["namespace"] or "default"
        kind = entity["kind"]
        entity["metadata"]["identifier"] = f"{kind}:{namespace}/{name}".lower()
        return entity

    async def _get_paginated_entities(
        self, kind: str, cursor: Optional[str] = None, page_size: int = PAGE_SIZE
    ) -> Any:
        params = {"limit": page_size, "filter": f"kind={kind}"}
        if cursor:
            params["cursor"] = cursor
        response = await self.client.get(self.entities_query_endpoint, params=params)  # type: ignore
        response.raise_for_status()

        parsed_response = response.json()
        next_cursor = parsed_response.get("pageInfo", {}).get("nextCursor")
        total = parsed_response.get("totalItems")
        entities: List[Any] = parsed_response.get("items", [])

        return next_cursor, total, [self._add_identifier(entity) for entity in entities]

    async def get_all_entities_by_kind(self, kind: str) -> Any:
        cursor = None
        while True:
            next_cursor, total, entities = await self._get_paginated_entities(
                kind, cursor
            )
            logger.info(f"Processing {len(entities)} {kind}s out of {total}")
            yield entities

            cursor = next_cursor
            if not cursor:
                break
