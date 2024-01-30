from enum import StrEnum
from typing import Any, AsyncGenerator

import httpx
from loguru import logger
from port_ocean.utils import http_async_client


class ResourceKey(StrEnum):
    PROBLEM = "problem"
    SLO = "slo"
    ENTITY_TYPE = "entity_type"
    ENTITY = "entity"


class DynatraceClient:
    def __init__(self, host_url: str, api_key: str) -> None:
        self.host_url = f"{host_url.rstrip('/')}/api/v2"
        self.client = http_async_client
        self.client.headers.update({"Authorization": f"Api-Token {api_key}"})

    async def _get_paginated_resources(
        self, url: str, resource_key: str, params: dict[str, Any] = {}
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info(f"Fetching {resource_key} from {url} with params {params}")
        try:
            while True:
                response = await self.client.get(url, params=params)
                response.raise_for_status()
                response_data = response.json()
                resources = response_data[resource_key]
                yield resources
                next_page_key = response_data.get("nextPageKey")
                if not next_page_key:
                    break
                params = {"nextPageKey": next_page_key}
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error on {url}: {e.response.status_code} - {e.response.text}"
            )
            raise
        except httpx.HTTPError as e:
            logger.error(f"HTTP error on {url}: {e}")
            raise

    async def get_problems(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for problems in self._get_paginated_resources(
            f"{self.host_url}/problems", "problems"
        ):
            yield problems

    async def get_slos(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for slos in self._get_paginated_resources(f"{self.host_url}/slo", "slo"):
            yield slos

    async def _get_entity_types(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for entity_types in self._get_paginated_resources(
            f"{self.host_url}/entityTypes", "types"
        ):
            yield entity_types

    async def _get_entities_from_type(
        self, type_: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for entities in self._get_paginated_resources(
            f"{self.host_url}/entities",
            "entities",
            params={"entitySelector": f'type("{type_}")'},
        ):
            yield entities

    async def get_entities(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for entity_types in self._get_entity_types():
            for entity_type in entity_types:
                async for entities in self._get_entities_from_type(entity_type["type"]):
                    yield entities

    async def get_single_problem(self, problem_id: str) -> dict[str, Any]:
        url = f"{self.host_url}/problems/{problem_id}"
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error on {url}: {e.response.status_code} - {e.response.text}"
            )
            raise
        except httpx.HTTPError as e:
            logger.error(f"HTTP error on {url}: {e}")
            raise
