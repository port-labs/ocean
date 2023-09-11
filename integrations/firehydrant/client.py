from typing import Any, Optional, AsyncGenerator
import httpx
from loguru import logger
from datetime import datetime

PAGE_SIZE = 50

endpoint_resource_type_mapper = {
    "environment": "environments",
    "service": "services",
    "incident": "incidents",
    "retrospective": "post_mortems/reports",
}


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
        return await self.send_api_request(endpoint=f"incidents/{incident_id}")

    async def get_single_service(self, service_id: str) -> dict[str, Any]:
        serice_data = await self.send_api_request(endpoint=f"services/{service_id}")
        service_analytics_data = await self.compute_service_mean_time_metrics(
            serice_data["active_incidents"]
        )
        serice_data["__incidentMetrics"] = service_analytics_data
        return serice_data

    async def get_single_environment(self, environment_id: str) -> dict[str, Any]:
        return await self.send_api_request(endpoint=f"environments/{environment_id}")

    async def get_single_retrospective(self, report_id: str) -> dict[str, Any]:
        report_data = await self.send_api_request(
            endpoint=f"post_mortems/reports/{report_id}"
        )
        enriched_data = await self.enrich_incident_report_data(report_data)
        report_data["__enrichedData"] = enriched_data
        return report_data

    async def enrich_incident_report_data(
        self, report: dict[str, Any]
    ) -> dict[str, Any]:
        ## get incident taskS
        incident_id = report.get("incident", {}).get("id")
        tasks = await self.get_tasks_by_incident(incident_id=incident_id)

        ## get incident duration data
        milestones = report.get("incident", {}).get("milestones", [])
        incident_duration = await self.compute_incident_duration(milestones=milestones)

        return {
            "tasks": tasks,
            "duration": incident_duration,
        }

    async def get_tasks_by_incident(self, incident_id: str) -> list[dict[str, Any]]:
        logger.info(f"Getting tasks details for incident: {incident_id}")
        task_endpoint = f"incidents/{incident_id}/tasks"
        tasks = []

        async for item in self.get_paginated_resource(task_endpoint):
            tasks.extend(item)
        return tasks

    async def compute_incident_duration(
        self, milestones: list[dict[str, Any]]
    ) -> Optional[float]:
        started_time = None
        resolved_time = None

        # Iterate through the milestones to find the "started" and "resolved" events.
        for milestone in milestones:
            event_type = milestone.get("type")
            occurred_at = milestone.get("occurred_at", "")

            # Check if the event is a "started" event.
            if event_type == "started":
                started_time = datetime.fromisoformat(occurred_at[:-1])

            # Check if the event is a "resolved" event.
            if event_type == "resolved":
                resolved_time = datetime.fromisoformat(occurred_at[:-1])

        # Calculate the duration if both "started" and "resolved" events are found.
        if started_time and resolved_time:
            duration = resolved_time - started_time
            duration_hours = duration.total_seconds() / 60  # Convert to minutes
            return round(duration_hours, 2)

        return None

    async def compute_service_mean_time_metrics(
        self, active_incidents_ids: list[Any]
    ) -> dict[str, Any]:
        if len(active_incidents_ids) == 0:
            return {}

        service_metrics = {
            "time_to_acknowledge": 0,
            "time_to_identify": 0,
            "time_to_mitigate": 0,
            "time_to_resolve": 0,
        }

        for incident_id in active_incidents_ids:
            incident_data = await self.get_single_incident(incident_id=incident_id)
            milestones = incident_data.get("milestones", {})
            incident_metrics = await self.compute_incident_analytics_metrics(
                milestones=milestones
            )

            # Update the cumulative metrics for the service
            for metric_name, metric_value in incident_metrics.items():
                service_metrics[metric_name] += metric_value

        # Calculate the average metrics for the service
        for metric_name in service_metrics:
            service_metrics[metric_name] //= len(active_incidents_ids)

        return service_metrics

    async def compute_incident_analytics_metrics(
        self, milestones: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Compute incident analytics metrics based on milestone data. Formular retrieved from https://firehydrant.com/docs/managing-incidents/incident-metrics/
        """

        incident_times = {
            "started": None,
            "acknowledged": None,
            "mitigated": None,
            "identified": None,
            "resolved": None,
        }

        for event in milestones:
            incident_type = event["type"]
            occurred_at = datetime.fromisoformat(event.get("occurred_at", ""))

            if incident_type in incident_times:
                if incident_times[incident_type] is None:
                    incident_times[incident_type] = occurred_at  # type: ignore
            else:
                continue  # Ignore unknown incident types
        result: dict[str, Any] = {}

        if incident_times["started"] and incident_times["acknowledged"]:
            time_to_acknowledge = (
                incident_times["acknowledged"] - incident_times["started"]
            ).total_seconds()
            result["time_to_acknowledge"] = int(time_to_acknowledge / 60)

        if incident_times["started"] and incident_times["identified"]:
            time_to_identify = (
                incident_times["identified"] - incident_times["started"]
            ).total_seconds()
            result["time_to_identify"] = int(time_to_identify / 60)

        if incident_times["started"] and incident_times["mitigated"]:
            time_to_acknowledge = (
                incident_times["mitigated"] - incident_times["started"]
            ).total_seconds()
            result["time_to_mitigate"] = int(time_to_acknowledge / 60)

        if incident_times["started"] and incident_times["resolved"]:
            time_to_resolve = (
                incident_times["resolved"] - incident_times["started"]
            ).total_seconds()
            result["time_to_resolve"] = int(time_to_resolve / 60)

        return result

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
