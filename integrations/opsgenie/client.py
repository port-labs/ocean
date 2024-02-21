from typing import Any, AsyncGenerator, Optional

import httpx
from loguru import logger

from port_ocean.context.event import event
from port_ocean.utils import http_async_client
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

    async def get_paginated_resources(
        self, resource_type: ObjectKind
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        cache_key = resource_type.value

        if cache := event.attributes.get(cache_key):
            yield cache
            return
        api_version = await self.get_resource_api_version(resource_type)
        url = f"{self.api_url}/{api_version}/{resource_type.value}s"
        pagination_params: dict[str, Any] = {"limit": PAGE_SIZE}
        resources_list = []
        while url:
            try:
                response = await self._get_single_resource(
                    url=url, query_params=pagination_params
                )
                batch_data = response["data"]
                resources_list.extend(batch_data)
                yield batch_data

                url = response.get("paging", {}).get("next")
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
                )
                raise
        event.attributes[cache_key] = resources_list

    async def get_alert(self, identifier: str) -> dict[str, Any]:
        api_version = await self.get_resource_api_version(ObjectKind.ALERT)
        url = f"{self.api_url}/{api_version}/alerts/{identifier}"
        alert_data = (await self._get_single_resource(url))["data"]
        return await self.get_related_incident_by_alert(alert_data)

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

    async def get_schedule_by_team(
        self, team_identifier: str
    ) -> Optional[dict[str, Any]]:
        schedules = []
        async for schedule_batch in self.get_paginated_resources(ObjectKind.SCHEDULE):
            schedules.extend(schedule_batch)
        return next(
            (
                schedule
                for schedule in schedules
                if schedule["ownerTeam"]["id"] == team_identifier
            ),
            {},
        )

    async def get_associated_alerts(
        self, incident_identifier: str
    ) -> list[dict[str, Any]]:
        cache_key = f"{ObjectKind.INCIDENT}-{incident_identifier}"
        if cache := event.attributes.get(cache_key):
            return cache

        api_version = await self.get_resource_api_version(ObjectKind.INCIDENT)
        url = f"{self.api_url}/{api_version}/incidents/{incident_identifier}/associated-alert-ids"
        associated_alerts = (await self._get_single_resource(url))["data"]
        event.attributes[cache_key] = associated_alerts
        return associated_alerts

    async def get_impacted_services(
        self, impacted_service_ids: list[str]
    ) -> list[dict[str, Any]]:
        services = []
        async for service_batch in self.get_paginated_resources(ObjectKind.SERVICE):
            services.extend(service_batch)
        service_dict = {service["id"]: service for service in services}
        services_data = [
            service_dict[service_id]
            for service_id in impacted_service_ids
            if service_id in service_dict
        ]
        return services_data

    async def get_related_incident_by_alert(
        self, alert: dict[str, Any]
    ) -> dict[str, Any]:
        incidents = []
        async for incident_batch in self.get_paginated_resources(ObjectKind.INCIDENT):
            incidents.extend(incident_batch)

        for incident in incidents:
            associated_alerts = await self.get_associated_alerts(incident["id"])
            if alert["id"] in associated_alerts:
                alert["__relatedIncident"] = incident
                break  # Stop searching once a related incident is found

        return alert
