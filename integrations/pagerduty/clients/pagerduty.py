from typing import Any, AsyncGenerator

import httpx
from loguru import logger

from port_ocean.utils import http_async_client
from port_ocean.context.event import event
from .utils import get_date_range_for_last_n_months

USER_KEY = "users"


class PagerDutyClient:
    def __init__(self, token: str, api_url: str, app_host: str | None):
        self.token = token
        self.api_url = api_url
        self.app_host = app_host
        self.http_client = http_async_client
        self.http_client.headers.update(self.api_auth_param["headers"])

    @property
    def incident_upsert_events(self) -> list[str]:
        return [
            "incident.acknowledged",
            "incident.annotated",
            "incident.delegated",
            "incident.escalated",
            "incident.priority_updated",
            "incident.reassigned",
            "incident.reopened",
            "incident.resolved",
            "incident.status_update_published",
            "incident.responder.added",
            "incident.responder.replied",
            "incident.triggered",
            "incident.unacknowledged",
        ]

    @property
    def service_upsert_events(self) -> list[str]:
        return [
            "service.created",
            "service.updated",
        ]

    @property
    def service_delete_events(self) -> list[str]:
        return [
            "service.deleted",
        ]

    @property
    def all_events(self) -> list[str]:
        return (
            self.incident_upsert_events
            + self.service_upsert_events
            + self.service_delete_events
        )

    @property
    def api_auth_param(self) -> dict[str, Any]:
        return {
            "headers": {
                "Authorization": f"Token token={self.token}",
                "Content-Type": "application/json",
            }
        }

    async def paginate_request_to_pager_duty(
        self, data_key: str, params: dict[str, Any] | None = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        url = f"{self.api_url}/{data_key}"
        offset = 0
        has_more_data = True

        while has_more_data:
            try:
                response = await self.http_client.get(
                    url, params={"offset": offset, **(params or {})}
                )
                response.raise_for_status()
                data = response.json()
                yield data[data_key]

                has_more_data = data["more"]
                if has_more_data:
                    offset += data["limit"]
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
                )
                raise
            except httpx.HTTPError as e:
                logger.error(f"HTTP occurred while fetching paginated data: {e}")
                raise

    async def get_singular_from_pager_duty(
        self, object_type: str, identifier: str
    ) -> dict[str, Any]:
        url = f"{self.api_url}/{object_type}/{identifier}"

        try:
            response = await self.http_client.get(url)
            response.raise_for_status()
            data = response.json()
            return data
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
            )
            raise
        except httpx.HTTPError as e:
            logger.error(f"HTTP occurred while fetching data: {e}")
            raise

    async def create_webhooks_if_not_exists(self) -> None:
        if not self.app_host:
            logger.warning(
                "No app host provided, skipping webhook creation. "
                "Without setting up the webhook, the integration will not export live changes from PagerDuty"
            )
            return

        invoke_url = f"{self.app_host}/integration/webhook"
        async for subscriptions in self.paginate_request_to_pager_duty(
            data_key="webhook_subscriptions"
        ):
            for webhook in subscriptions:
                if webhook["delivery_method"]["url"] == invoke_url:
                    return

        body = {
            "webhook_subscription": {
                "delivery_method": {
                    "type": "http_delivery_method",
                    "url": invoke_url,
                },
                "description": "Port Ocean Integration",
                "events": self.all_events,
                "filter": {"type": "account_reference"},
                "type": "webhook_subscription",
            }
        }

        try:
            await self.http_client.post(
                f"{self.api_url}/webhook_subscriptions", json=body
            )
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
            )
        except httpx.HTTPError as e:
            logger.error(f"HTTP occurred while creating webhook subscription {e}")
            raise

    async def get_oncall_user(
        self, *escalation_policy_ids: str
    ) -> list[dict[str, Any]]:
        logger.info(
            f"Fetching who is oncall for escalation poilices: {','.join(escalation_policy_ids)}"
        )
        params = {
            "escalation_policy_ids[]": escalation_policy_ids,
            "include[]": "users",
        }
        oncalls = []

        async for oncall_batch in self.paginate_request_to_pager_duty(
            data_key="oncalls", params=params
        ):
            logger.info(f"Received oncalls with batch size {len(oncall_batch)}")
            oncalls.extend(oncall_batch)

        return oncalls

    async def update_oncall_users(
        self, services: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        services_names = [service["name"] for service in services]
        logger.info(
            f"Fetching and matching who is on-call for {len(services)} services: {services_names}"
        )
        oncall_users = await self.get_oncall_user(
            *[service["escalation_policy"]["id"] for service in services]
        )

        for service in services:
            escalation_policy_id = service["escalation_policy"]["id"]

            service["__oncall_user"] = [
                user
                for user in oncall_users
                if user["escalation_policy"]["id"] == escalation_policy_id
            ]
        return services

    async def get_incident_analytics(self, incident_id: str) -> dict[str, Any]:
        logger.info(f"Fetching analytics for incident: {incident_id}")
        url = f"{self.api_url}/analytics/raw/incidents/{incident_id}"

        try:
            response = await self.http_client.get(url)
            response.raise_for_status()
            data = response.json()
            return data
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.debug(
                    f"Incident {incident_id} analytics data was not found, skipping..."
                )
                return {}

            logger.error(
                f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
            )
            return {}
        except httpx.HTTPError as e:
            logger.error(f"HTTP occurred while fetching incident analytics data: {e}")
            return {}

    async def get_service_analytics(
        self, service_id: str, months_period: int = 3
    ) -> dict[str, Any]:
        logger.info(f"Fetching analytics for service: {service_id}")
        url = f"{self.api_url}/analytics/metrics/incidents/services"
        date_ranges = get_date_range_for_last_n_months(months_period)

        try:
            body = {
                "filters": {
                    "service_ids": [service_id],
                    "created_at_start": date_ranges[0],
                    "created_at_end": date_ranges[1],
                }
            }
            response = await self.http_client.post(url, json=body)
            response.raise_for_status()

            logger.info(f"Successfully fetched analytics for service: {service_id}")

            return response.json()["data"][0] if response.json()["data"] else {}

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.debug(
                    f"Service {service_id} analytics data was not found, skipping..."
                )
                return {}

            logger.error(
                f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
            )
            return {}
        except httpx.HTTPError as e:
            logger.error(f"HTTP occurred while fetching service analytics data: {e}")
            return {}

    async def fetch_and_cache_users(self) -> None:
        async for users in self.paginate_request_to_pager_duty(data_key=USER_KEY):
            for user in users:
                event.attributes[user["id"]] = user["email"]

    def get_cached_user(self, user_id: str) -> dict[str, Any] | None:
        return event.attributes.get(user_id)

    async def transform_user_ids_to_emails(
        self, schedules: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        await self.fetch_and_cache_users()

        for schedule in schedules:
            for user in schedule.get(USER_KEY, []):
                cached_user = self.get_cached_user(user["id"])
                if cached_user:
                    user["__email"] = cached_user
                else:
                    logger.debug(f"User ID {user['id']} not found in user cache")
        return schedules
