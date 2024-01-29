from enum import StrEnum
from typing import Any, AsyncGenerator

import httpx
from loguru import logger
from port_ocean.context.event import event
from port_ocean.utils import http_async_client


class ResourceKey(StrEnum):
    PROBLEM = "problem"
    SLO = "slo"
    ENTITY_TYPE = "entity_type"
    ENTITY = "entity"


class DynatraceClient:
    def __init__(self, host_url: str, api_key: str) -> None:
        self.host_url = host_url
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

    async def _get_problems(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for problems in self._get_paginated_resources(
            f"{self.host_url}/api/v2/problems", "problems"
        ):
            yield problems

    async def _get_slos(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for slos in self._get_paginated_resources(
            f"{self.host_url}/api/v2/slo", "slo"
        ):
            yield slos

    async def _get_entity_types(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for entity_types in self._get_paginated_resources(
            f"{self.host_url}/api/v2/entityTypes", "types"
        ):
            yield entity_types

    async def _get_entities_from_type(
        self, type: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for entities in self._get_paginated_resources(
            f"{self.host_url}/api/v2/entities",
            "entities",
            params={"entitySelector": f'type("{type}")'},
        ):
            yield entities

    async def _get_entities(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for entity_types in self._get_entity_types():
            for entity_type in entity_types:
                async for entities in self._get_entities_from_type(entity_type["type"]):
                    yield entities

    async def get_resource(
        self, resource: str, **kwargs: dict[str, Any]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        RESOURCE_MAPPING = {
            ResourceKey.PROBLEM.value: self._get_problems,
            ResourceKey.SLO.value: self._get_slos,
            ResourceKey.ENTITY.value: self._get_entities,
        }

        if cache := event.attributes.get(resource):
            logger.info(f"picking {resource} from cache")
            yield cache
            return

        async for resources in RESOURCE_MAPPING[resource]():
            event.attributes.setdefault(resource, []).extend(resources)
            yield resources
