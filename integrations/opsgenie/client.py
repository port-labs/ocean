from typing import Any, AsyncGenerator, Optional
import asyncio
import httpx
from loguru import logger

from port_ocean.utils import http_async_client
from port_ocean.utils.cache import cache_iterator_result
from utils import ObjectKind, RESOURCE_API_VERSIONS

PAGE_SIZE = 100
CONCURRENT_REQUESTS = 5
MAX_OPSGENIE_OFFSET_LIMIT = 20000


class OpsGenieClient:
    def __init__(self, token: str, api_url: str):
        self.token = token
        self.api_url = api_url
        self.http_client = http_async_client
        self.http_client.headers.update(self.api_auth_header)
        self.semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)

    @property
    def api_auth_header(self) -> dict[str, Any]:
        return {"Authorization": f"GenieKey {self.token}"}

    async def get_resource_api_version(self, resource_type: ObjectKind) -> str:
        return RESOURCE_API_VERSIONS.get(resource_type, "v2")

    def get_resource_offset_limit(self, resource_type: ObjectKind) -> Optional[int]:
        resource_types_with_limit = {
            ObjectKind.ALERT,
            ObjectKind.INCIDENT,
            ObjectKind.SERVICE,
        }
        return (
            MAX_OPSGENIE_OFFSET_LIMIT
            if resource_type in resource_types_with_limit
            else None
        )

    async def _get_single_resource(
        self,
        url: str,
        query_params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        async with self.semaphore:
            try:
                logger.info(
                    f"Fetching data from {url} with query params {query_params}"
                )
                response = await self.http_client.get(url=url, params=query_params)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
                )
                raise
            except httpx.HTTPError as e:
                logger.error(
                    f"Encountered an HTTP error while fetching request for url {url} error: {e}"
                )
                raise

    @cache_iterator_result()
    async def get_paginated_resources(
        self, resource_type: ObjectKind, query_params: Optional[dict[str, Any]] = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        api_version = await self.get_resource_api_version(resource_type)
        url = f"{self.api_url}/{api_version}/{resource_type.value}s"

        request_params: dict[str, Any] = {"limit": PAGE_SIZE, **(query_params or {})}
        current_offset = 0

        while url:
            max_offset_limit = self.get_resource_offset_limit(resource_type)
            if max_offset_limit is not None and current_offset >= max_offset_limit:
                logger.warning(
                    f"Stopped pagination for {resource_type.value}s at offset {current_offset}: "
                    f"reached OpsGenie API limit of {max_offset_limit}"
                )
                break

            try:
                params = request_params if current_offset == 0 else None
                response = await self._get_single_resource(url=url, query_params=params)
                yield response["data"]

                url = response.get("paging", {}).get("next")
                current_offset += PAGE_SIZE
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
                )
                raise
            except httpx.HTTPError as e:
                logger.error(
                    f"Encountered an HTTP error while fetching request for url {url} error: {e}"
                )
                raise

    async def get_alert(self, identifier: str) -> dict[str, Any]:
        logger.debug(f"Fetching alert {identifier}")
        api_version = await self.get_resource_api_version(ObjectKind.ALERT)
        url = f"{self.api_url}/{api_version}/alerts/{identifier}"
        alert_data = (await self._get_single_resource(url))["data"]
        return alert_data

    async def get_oncall_users(self, schedule_identifier: str) -> dict[str, Any]:
        logger.debug(f"Fetching on-call users for schedule {schedule_identifier}")

        api_version = await self.get_resource_api_version(ObjectKind.SCHEDULE)
        url = f"{self.api_url}/{api_version}/schedules/{schedule_identifier}/on-calls?flat=true"
        return (await self._get_single_resource(url))["data"]

    async def get_team_members(self, team_identifier: str) -> dict[str, Any]:
        logger.info(f"Fetching members for team {team_identifier}")

        api_version = await self.get_resource_api_version(ObjectKind.TEAM)
        url = f"{self.api_url}/{api_version}/teams/{team_identifier}"
        return (await self._get_single_resource(url))["data"].get("members", [])
