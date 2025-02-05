from enum import StrEnum
from typing import Any, AsyncGenerator

import httpx
from loguru import logger
from port_ocean.utils import http_async_client

from integration import EntityFieldsType
import asyncio

# SLOs by default are not evaluated and the initial state
# at creation is being returned in the SLO list API.
# To force evaluation, we must pass the `evaluate` query parameter,
# setting it to `true`. This will return the current state of the SLOs.
# The maximum page size for the SLO list API when it is evaluated is 25.
EVALUATED_SLO_MAX_PAGE_SIZE = 25


class ResourceKey(StrEnum):
    PROBLEM = "problem"
    SLO = "slo"
    ENTITY = "entity"


class DynatraceClient:
    def __init__(self, host_url: str, api_key: str) -> None:
        self.host = host_url.rstrip("/")
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
                logger.info(f"Received batch with {len(resources)} {resource_key}")
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
            f"{self.host_url}/problems", "problems", {"pageSize": 200}
        ):
            yield problems

    async def get_slos(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for slos in self._get_paginated_resources(
            f"{self.host_url}/slo",
            "slo",
            {"pageSize": EVALUATED_SLO_MAX_PAGE_SIZE, "evaluate": "true"},
        ):
            yield slos

    async def get_entities(
        self, selectory_query: str, entity_fields: EntityFieldsType | None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        params = {
            "entitySelector": selectory_query,
            "pageSize": 100,
        }
        if entity_fields:
            params["fields"] = entity_fields

        async for entities in self._get_paginated_resources(
            f"{self.host_url}/entities",
            "entities",
            params=params,
        ):
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

    async def _get_slo_related_entities(self, query: str) -> list[dict[str, Any]]:
        related_entities = []
        try:
            async for entities_batch in self.get_entities(query, None):
                related_entities.extend(entities_batch)
            return related_entities
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error on fetching related entities: {e.response.text}")
            raise
        except httpx.HTTPError as e:
            logger.error(f"HTTP error on fetching related entities: {e}")
            raise

    async def enrich_slos_with_related_entities(
        self, slos: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        logger.info(f"Fetching related entities for {len(slos)} slos")

        related_slo_tasks = [
            self._get_slo_related_entities(slo["filter"]) for slo in slos
        ]
        results = await asyncio.gather(*related_slo_tasks)

        for slo, entities in zip(slos, results):
            slo["__entities"] = entities
        return slos

    async def get_teams(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for teams in self._get_paginated_resources(
            f"{self.host_url}/settings/objects",
            "items",
            {"schemaIds": "builtin:ownership.teams"},
        ):
            yield teams

    async def healthcheck(self) -> None:
        try:
            response = await self.client.get(
                f"{self.host}/api/v1/config/clusterversion"
            )
            response.raise_for_status()
            logger.info("Dynatrace sanity check passed")
            logger.info(f"Connected to Dynatrace version {response.json()['version']}")
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Integration failed to connect to Dynatrace instance as part of sanity check due to HTTP error: {e.response.status_code} and response text: {e.response.text}"
            )
            raise
        except httpx.HTTPError:
            logger.exception(
                "Integration failed to connect to Dynatrace instance as part of sanity check due to HTTP error"
            )
            raise
