from enum import StrEnum
from typing import Any, Optional, AsyncGenerator, Union

import httpx
from loguru import logger

from port_ocean.context.event import event
from port_ocean.utils import http_async_client
from utils import ObjectKind, RESOURCE_API_PATH_MAPPER

PAGE_SIZE = 50

endpoint_resource_type_mapper = {
    "environment": "environments",
    "service": "services",
    "incident": "incidents",
    "retrospective": "post_mortems/reports",
}


class CacheKeys(StrEnum):
    INCIDENT = "incident"


class FirehydrantClient:
    def __init__(self, base_url: str, api_key: str, app_host: str):
        self.base_url = base_url
        self.api_key = api_key
        self.app_host = app_host
        self.http_client = http_async_client
        self.http_client.headers.update(self.api_auth_header)

    @property
    def api_auth_header(self) -> dict[str, Any]:
        return {
            "Authorization": f"{self.api_key}",
            "Content-Type": "application/json",
        }

    async def send_api_request(
        self,
        endpoint: str,
        method: str = "GET",
        query_params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        try:
            response = await self.http_client.request(
                method=method,
                url=f"{self.base_url}/v1/{endpoint}",
                params=query_params,
                json=json_data,
                headers=self.api_auth_header,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
            )
            raise

    async def get_paginated_resource(
        self,
        resource_type: Union[ObjectKind, str],
        additional_params: dict[str, Any] = {},
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        if isinstance(resource_type, ObjectKind):
            endpoint = RESOURCE_API_PATH_MAPPER.get(resource_type, resource_type.value)
        elif isinstance(resource_type, str):
            endpoint = resource_type
        else:
            raise ValueError(
                "Invalid resource parameter. It should be ObjectKind or a string endpoint."
            )
        logger.info(f"Fetching {endpoint} from Firehydrant")

        pagination_params: dict[str, Any] = {
            "page": 1,
            "per_page": PAGE_SIZE,
        }
        pagination_params.update(additional_params)

        try:
            while True:
                response = await self.send_api_request(
                    endpoint=endpoint, query_params=pagination_params
                )
                yield response["data"]

                pagination_params["page"] += 1

                if pagination_params["page"] > response["pagination"]["pages"]:
                    break

        except httpx.HTTPError as e:
            logger.error(f"Error while fetching {resource_type}: {str(e)}")

    async def get_single_environment(self, environment_id: str) -> dict[str, Any]:
        return await self.send_api_request(endpoint=f"environments/{environment_id}")

    async def get_single_incident(self, incident_id: str) -> dict[str, Any]:
        cache_key = f"{CacheKeys.INCIDENT}-{incident_id}"
        if cache := event.attributes.get(cache_key):
            return cache
        incident_data = await self.send_api_request(endpoint=f"incidents/{incident_id}")
        event.attributes[cache_key] = incident_data
        return incident_data

    async def get_single_service(self, service_id: str) -> list[dict[str, Any]]:
        service_data = await self.send_api_request(endpoint=f"services/{service_id}")
        return await self.get_incident_milestones(services=[service_data])

    async def get_single_retrospective(self, report_id: str) -> dict[str, Any]:
        report_data = await self.send_api_request(
            endpoint=f"post_mortems/reports/{report_id}"
        )
        incident_id = report_data["incident"]["id"]
        tasks = await self.get_tasks_by_incident(incident_id=incident_id)
        report_data["__incident"] = {"tasks": tasks}
        return report_data

    async def get_tasks_by_incident(self, incident_id: str) -> list[dict[str, Any]]:
        logger.info(f"Getting tasks details for incident: {incident_id}")
        task_endpoint = f"incidents/{incident_id}/tasks"
        tasks = []
        async for item in self.get_paginated_resource(task_endpoint):
            tasks.extend(item)
        return tasks

    async def get_incident_milestones(
        self, services: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        incidents = []
        service_ids = [service["id"] for service in services]

        pagination_params: dict[str, Any] = {"services": ",".join(service_ids)}

        async for batched_incidents in self.get_paginated_resource(
            ObjectKind.INCIDENT, additional_params=pagination_params
        ):
            incidents.extend(batched_incidents)

        service_milestones: dict[str, Any] = {
            service_id: [] for service_id in service_ids
        }

        for incident in incidents:
            for service_data in incident["services"]:
                service_id = service_data["id"]
                if service_id in service_milestones:
                    service_milestones[service_id].append(incident["milestones"])
        for service in services:
            service["__incidents"] = {"milestones": service_milestones[service["id"]]}

        return services

    async def create_webhooks_if_not_exists(self) -> None:
        webhook_endpoint = "webhooks"
        all_subscriptions = []

        async for item in self.get_paginated_resource(webhook_endpoint):
            all_subscriptions.extend(item)

        app_host_webhook_url = f"{self.app_host}/integration/webhook"

        for webhook in all_subscriptions:
            if webhook["url"] == app_host_webhook_url:
                return

        body = {
            "url": app_host_webhook_url,
            "state": "active",
            "subscriptions": ["incidents", "change_events"],
        }

        await self.send_api_request(
            endpoint=webhook_endpoint, method="POST", json_data=body
        )
