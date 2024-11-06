from typing import Any, AsyncGenerator, Optional

import httpx
from loguru import logger

from port_ocean.utils import http_async_client
from port_ocean.utils.cache import cache_iterator_result
from utils import ObjectKind, RESOURCE_API_VERSIONS

PAGE_SIZE = 100


class OpsGenieClient:
    def __init__(self, token: str, api_url: str):
        self.token = token
        self.api_url = api_url
        self.http_client = http_async_client
        self.http_client.headers.update(self.api_auth_header)

    @property
    def api_auth_header(self) -> dict[str, Any]:
        return {"Authorization": f"GenieKey {self.token}"}

    async def get_resource_api_version(self, resource_type: ObjectKind) -> str:
        return RESOURCE_API_VERSIONS.get(resource_type, "v2")

    async def _get_single_resource(
        self,
        url: str,
        query_params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        try:
            response = await self.http_client.get(url=url, params=query_params)
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
            )
            raise

    @cache_iterator_result()
    async def get_paginated_resources(
        self, resource_type: ObjectKind, query_params: Optional[dict[str, Any]] = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        api_version = await self.get_resource_api_version(resource_type)
        url = f"{self.api_url}/{api_version}/{resource_type.value}s"

        pagination_params: dict[str, Any] = {"limit": PAGE_SIZE, **(query_params or {})}
        while url:
            try:
                logger.info(
                    f"Fetching data from {url} with query params {pagination_params}"
                )
                response = await self._get_single_resource(
                    url=url, query_params=pagination_params
                )
                yield response["data"]

                url = response.get("paging", {}).get("next")
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
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
