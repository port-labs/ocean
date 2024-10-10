from typing import Any, List, Optional

from loguru import logger

from port_ocean.utils import http_async_client

PAGE_SIZE = 20

class BackstageClient:
    BASE_ENDPOINT = "api/catalog/entities/by-query"

    def __init__(self, backstage_host, backstage_token) -> None:
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
       self, page_size: int, kind: str, end_cursor: Optional[str] = None) -> Any:
        params = {"limit": page_size, "filter": f"kind={kind}"}
        if end_cursor:
            params["cursor"] = end_cursor
        response = await self.client.get(self.entities_query_endpoint, params=params)
        response.raise_for_status()

        parsed_response = response.json()
        next_cursor = parsed_response.get("pageInfo", {}).get("nextCursor")
        total = parsed_response.get("totalItems")
        entities: List[Any] = parsed_response.get("items", [])

        return {
            "next_cursor": next_cursor,
            "total": total,
            "entities": [self._add_identifier(entity) for entity in entities]
        }

    async def get_entities_by_kind(self, kind: str, end_cursor: Optional[str] = None):
       return await self._get_paginated_entities(PAGE_SIZE, kind, end_cursor)

    async def get_all_entities_by_kind(self, kind: str):
        end_cursor = None
        while True:
            response = await self.get_entities_by_kind(kind, end_cursor)
            yield response["entities"]

            end_cursor = response["next_cursor"]
            if not end_cursor:
                break
