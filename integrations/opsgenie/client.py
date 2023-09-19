from typing import Any, AsyncGenerator, Optional
import httpx
from loguru import logger
from utils import ObjectKind, RESOURCE_API_VERSIONS

PAGE_SIZE = 50


class OpsGenieClient:
    def __init__(self, token: str, api_url: str):
        self.token = token
        self.api_url = api_url
        self.http_client = httpx.AsyncClient(headers=self.api_auth_header)

    @property
    def delete_alert_events(self) -> list[str]:
        return [
            "Delete",
        ]

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

    async def get_paginated_resources(
        self, resource_type: ObjectKind
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        api_version = await self.get_resource_api_version(resource_type)
        url = f"{self.api_url}/{api_version}/{resource_type.value}"
        pagination_params: dict[str, Any] = {"limit": PAGE_SIZE}

        while url:
            try:
                response = await self._get_single_resource(
                    url=url, query_params=pagination_params
                )
                if response.get("data"):
                    yield response["data"]

                url = response.get("paging", {}).get("next")
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
                )
                raise

    async def get_alert(self, identifier: str) -> dict[str, Any]:
        api_version = await self.get_resource_api_version(ObjectKind.ALERT)
        url = f"{self.api_url}/{api_version}/alerts/{identifier}"
        return (await self._get_single_resource(url))["data"]

    async def get_oncall_team(self, identifier: str) -> dict[str, Any]:
        api_version = await self.get_resource_api_version(ObjectKind.TEAM)
        url = f"{self.api_url}/{api_version}/teams/{identifier}"
        return (await self._get_single_resource(url))["data"]
