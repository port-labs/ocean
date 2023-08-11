from typing import Any

import httpx
from loguru import logger

PAGE_SIZEE = 50


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

    async def _get_single_resource(self, url: str) -> dict[str, Any]:
        try:
            response = await self.http_client.get(url)
            response.raise_for_status()
            return response.json()["data"]

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
            )
            raise

    async def get_paginated_resources(self, resource_type: str) -> list[Any]:
        url = f"{self.api_url}/{resource_type}"
        has_more_data = True
        all_data = []
        offset = 0

        while has_more_data:
            try:
                response = await self.http_client.get(
                    url, params={"offset": offset * PAGE_SIZEE}
                )
                response.raise_for_status()
                data = response.json()

                all_data.extend(data["data"])

                if "paging" in data and "next" in data["paging"]:
                    offset += 1
                else:
                    has_more_data = False
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
                )
                raise
        return all_data

    async def get_alert(self, identifier: str) -> dict[str, Any]:
        url = f"{self.api_url}/alerts/{identifier}"
        return await self._get_single_resource(url)

    async def get_oncall_user(self, identifier: str) -> dict[str, Any]:
        url = f"{self.api_url}/schedules/{identifier}/on-calls?flat=true"
        response = await self._get_single_resource(url)
        return response.get("onCallRecipients", [])

    async def update_oncall_users(
        self, schedules: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        logger.info("Fetching and matching who is on-call for schedules")

        for schedule in schedules[0:1]:
            oncall_users = await self.get_oncall_user(schedule["id"])
            schedule["oncall_users"] = oncall_users
        return schedules
