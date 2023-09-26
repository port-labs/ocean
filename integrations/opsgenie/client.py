from typing import Any, AsyncGenerator, Optional
import httpx
from loguru import logger
from utils import ObjectKind, RESOURCE_API_VERSIONS
from port_ocean.context.event import event


PAGE_SIZE = 50


class OpsGenieClient:
    def __init__(self, token: str, api_url: str):
        self.token = token
        self.api_url = api_url
        self.http_client = httpx.AsyncClient(headers=self.api_auth_header)

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
        if ObjectKind.INCIDENT in event.attributes:
            cached_incidents = event.attributes[ObjectKind.INCIDENT]
            yield cached_incidents
            return

        api_version = await self.get_resource_api_version(resource_type)
        url = f"{self.api_url}/{api_version}/{resource_type.value}s"
        pagination_params: dict[str, Any] = {"limit": PAGE_SIZE}

        while url:
            try:
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
        api_version = await self.get_resource_api_version(ObjectKind.ALERT)
        url = f"{self.api_url}/{api_version}/alerts/{identifier}"
        return (await self._get_single_resource(url))["data"]

    async def get_oncall_team(self, identifier: str) -> dict[str, Any]:
        cache_key = f"{ObjectKind.TEAM}-{identifier}"
        if cache := event.attributes.get(cache_key):
            return cache
        api_version = await self.get_resource_api_version(ObjectKind.TEAM)
        url = f"{self.api_url}/{api_version}/teams/{identifier}"
        oncall_team = (await self._get_single_resource(url))["data"]
        event.attributes[cache_key] = oncall_team
        return oncall_team

    async def get_oncall_user(self, schedule_identifier: str) -> dict[str, Any]:
        api_version = await self.get_resource_api_version(ObjectKind.SCHEDULE)
        url = f"{self.api_url}/{api_version}/schedules/{schedule_identifier}/on-calls?flat=true"
        return (await self._get_single_resource(url))["data"]

    async def get_schedules(self) -> list[dict[str, Any]]:
        cache_key = ObjectKind.SCHEDULE
        schedules = []
        if cache := event.attributes.get(cache_key):
            return cache
        async for schedule_batch in self.get_paginated_resources(ObjectKind.SCHEDULE):
            schedules.extend(schedule_batch)
        event.attributes[cache_key] = schedules
        return schedules

    async def get_schedule_by_team(
        self, team_identifier: str
    ) -> Optional[dict[str, Any]]:
        schedules = await self.get_schedules()
        for schedule in schedules:
            if schedule["ownerTeam"]["id"] == team_identifier:
                return schedule
        return {}

    async def get_associated_alerts(
        self, incident_identifier: str
    ) -> list[dict[str, Any]]:
        api_version = await self.get_resource_api_version(ObjectKind.INCIDENT)
        url = f"{self.api_url}/{api_version}/incidents/{incident_identifier}/associated-alert-ids"
        return (await self._get_single_resource(url))["data"]

    async def get_incidents(self) -> list[dict[str, Any]]:
        cache_key = ObjectKind.INCIDENT
        incidents = []
        if cache := event.attributes.get(cache_key):
            return cache
        async for incident_batch in self.get_paginated_resources(ObjectKind.INCIDENT):
            incidents.extend(incident_batch)
        event.attributes[cache_key] = incidents
        return incidents

    async def get_incidents_by_service(self, service_id: str) -> list[dict[str, Any]]:
        incidents = await self.get_incidents()
        impacted_services = []
        for incident in incidents:
            if service_id in incident["impactedServices"]:
                impacted_services.append(incident)
        return impacted_services
