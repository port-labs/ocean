from enum import StrEnum
from typing import Any, Optional, AsyncGenerator
import httpx
from loguru import logger
from port_ocean.context.event import event

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
        self.http_client = httpx.AsyncClient(headers=self.api_auth_header)

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
        self, resource_type: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info(f"Getting {resource_type} from Firehydrant")
        endpoint = endpoint_resource_type_mapper.get(resource_type, resource_type)

        pagination_params: dict[str, Any] = {
            "page": 1,
            "per_page": PAGE_SIZE,
        }

        try:
            while True:
                response = await self.send_api_request(
                    endpoint=endpoint, query_params=pagination_params
                )
                if response.get("data"):
                    yield response["data"]
                else:
                    logger.warning(f"No {resource_type} found in the response")

                pagination_params["page"] += 1

                if pagination_params["page"] > response.get("pagination", {}).get(
                    "pages"
                ):
                    break

        except Exception as e:
            logger.error(f"Error while fetching {resource_type}: {str(e)}")

    async def get_single_incident(self, incident_id: str) -> dict[str, Any]:
        cache_key = f"{CacheKeys.INCIDENT}-{incident_id}"
        if cache := event.attributes.get(cache_key):
            return cache
        incident_data = await self.send_api_request(endpoint=f"incidents/{incident_id}")
        event.attributes[cache_key] = incident_data
        return incident_data

    async def get_single_service(self, service_id: str) -> dict[str, Any]:
        serice_data = await self.send_api_request(endpoint=f"services/{service_id}")
        service_analytics_data = await self.get_milestones_by_incident(
            serice_data["active_incidents"]
        )
        serice_data["__incidents"] = service_analytics_data
        return serice_data

    async def get_single_environment(self, environment_id: str) -> dict[str, Any]:
        return await self.send_api_request(endpoint=f"environments/{environment_id}")

    async def get_single_retrospective(self, report_id: str) -> dict[str, Any]:
        report_data = await self.send_api_request(
            endpoint=f"post_mortems/reports/{report_id}"
        )
        incident_id = report_data["incident"]["id"]
        tasks = await self.get_tasks_by_incident(incident_id=incident_id)
        report_data["__incident"] = tasks
        return report_data

    async def get_tasks_by_incident(self, incident_id: str) -> dict[str, Any]:
        logger.info(f"Getting tasks details for incident: {incident_id}")
        task_endpoint = f"incidents/{incident_id}/tasks"
        tasks = []

        async for item in self.get_paginated_resource(task_endpoint):
            tasks.extend(item)
        return {"tasks": tasks}

    async def get_milestones_by_incident(
        self, active_incidents_ids: list[Any]
    ) -> dict[str, Any]:
        incident_milestones = []
        for incident_id in active_incidents_ids:
            incident_data = await self.get_single_incident(incident_id=incident_id)
            incident_milestones.append(incident_data["milestones"])

        return {"milestones": incident_milestones}

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
            "subscriptions": ["incidents", "change_event"],
        }

        await self.send_api_request(
            endpoint=webhook_endpoint, method="POST", json_data=body
        )
