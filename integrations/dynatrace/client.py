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
        self.client.headers = httpx.Headers({"Authorization": f"Api-Token {api_key}"})

    async def _get_problems(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        url = f"{self.host_url}/api/v2/problems"
        logger.info(f"Fetching problems from {url}")
        while True:
            problems_response = await self.client.get(url)
            problems_response.raise_for_status()
            response_data = problems_response.json()
            problems = response_data["problems"]
            yield problems
            next_page_key = response_data.get("nextPageKey")
            if not next_page_key:
                break
            url = f"{self.host_url}/api/v2/problems?nextPageKey={next_page_key}"

    async def _get_slos(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        url = f"{self.host_url}/api/v2/slo"
        logger.info(f"Fetching slos from {url}")
        while True:
            slos_response = await self.client.get(url)
            slos_response.raise_for_status()
            response_data = slos_response.json()
            slos = response_data["slos"]
            yield slos
            next_page_key = response_data.get("nextPageKey")
            if not next_page_key:
                break
            url = f"{self.host_url}/api/v2/slo?nextPageKey={next_page_key}"

    async def _get_entity_types(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        url = f"{self.host_url}/api/v2/entityTypes"
        logger.info(f"Fetching entity types from {url}")
        while True:
            entity_types_response = await self.client.get(url)
            entity_types_response.raise_for_status()
            response_data = entity_types_response.json()
            entity_types = response_data["types"]
            yield entity_types
            next_page_key = response_data.get("nextPageKey")
            if not next_page_key:
                break
            url = f"{self.host_url}/api/v2/entityTypes?nextPageKey={next_page_key}"

    async def _get_entities_from_type(
        self, type: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        url = f'{self.host_url}/api/v2/?entitySelector=type("{type}")'
        logger.info(f"Fetching entities from {url}")
        while True:
            entities_response = await self.client.get(url)
            entities_response.raise_for_status()
            response_data = entities_response.json()
            entities = response_data["entities"]
            yield entities
            next_page_key = response_data.get("nextPageKey")
            if not next_page_key:
                break
            url = f'{self.host_url}/api/v2/?entitySelector=type("{type}")&nextPageKey={next_page_key}'

    async def _get_entities(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for entity_types in self._get_entity_types():
            for entity_type in entity_types:
                async for entities in self._get_entities_from_type(entity_type["type"]):
                    yield entities

    async def get_resource(
        self, resource: ResourceKey, **kwargs: dict[str, Any]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        RESOURCE_MAPPING = {
            ResourceKey.PROBLEMS: self._get_problems,
            ResourceKey.SLOS: self._get_slos,
            ResourceKey.ENTITIES: self._get_entities,
            ResourceKey.ENTITY_TYPES: self._get_entity_types,
        }

        if cache := event.attributes.get(resource):
            logger.info(f"picking {resource} from cache")
            yield cache
            return

        async for resources in RESOURCE_MAPPING[resource]():
            event.attributes.setdefault(resource, []).extend(resources)
            yield resources
