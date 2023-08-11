from typing import Any

import httpx
from loguru import logger


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
        """
        Fetches a single resource from the given OpsGenie URL using an HTTP GET request.

        Args:
            url (str): The URL of the resource to fetch.

        Returns:
            dict[str, Any]: A dictionary containing the JSON response from the resource.
        """
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
        """
        Retrieves a list of paginated resources of the specified OpsGenie resource type.

        Args:
            resource_type (str): The type of resources to retrieve. eg alerts, schedules

        Returns:
            list[Any]: A list of paginated resources.
        """
        url = f"{self.api_url}/{resource_type}"
        all_data = []

        while (
            url
        ):  # loop as long as there is a "next" property in the paginated response from Opsgenie
            try:
                response = await self.http_client.get(url)
                response.raise_for_status()
                data = response.json()

                all_data.extend(data["data"])

                # Check if there is a "next" URL in the paging data
                url = data.get("paging", {}).get("next")
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
                )
                raise
        return all_data

    async def get_alert(self, identifier: str) -> dict[str, Any]:
        """
        Fetches details about a specific alert in OpsGenie.

        Args:
            identifier (str): The unique identifier of the alert.

        Returns:
            dict[str, Any]: A dictionary containing information about the alert.
        """
        url = f"{self.api_url}/alerts/{identifier}"
        return await self._get_single_resource(url)

    async def get_oncall_users(self, identifier: str) -> dict[str, Any]:
        """
        Fetches information about the on-call user(s) for a specific schedule identifier.

        Args:
            identifier (str): The identifier for which to retrieve on-call user information.

        Returns:
            dict[str, Any]: A dictionary containing on-call user information for the identifier.
        """
        url = f"{self.api_url}/schedules/{identifier}/on-calls?flat=true"
        response = await self._get_single_resource(url)
        return response.get("onCallRecipients", [])

    async def update_oncall_users(
        self, schedules: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Updates a list of schedules with on-call user information.

        Args:
            schedules (list[dict[str, Any]]): A list of schedule dictionaries.

        Returns:
            list[dict[str, Any]]: The updated list of schedules with on-call user information.
        """
        logger.info("Fetching and matching who is on-call for schedules")

        for schedule in schedules:
            oncall_users = await self.get_oncall_users(schedule["id"])
            schedule["oncall_users"] = oncall_users
        return schedules
