from typing import Any
import httpx
from loguru import logger


class PagerDutyClient:
    def __init__(self, token: str, api_url: str, app_host: str):
        self.token = token
        self.api_url = api_url
        self.app_host = app_host

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
    def api_auth_header(self) -> dict[str, Any]:
        return {"Authorization": f"Token token={self.token}"}

    async def paginate_request_to_pager_duty(self, data_key: str) -> list[Any]:
        url = f"{self.api_url}/{data_key}"
        all_data = []
        offset = 0
        has_more_data = True

        async with httpx.AsyncClient() as client:
            while has_more_data:
                try:
                    response = await client.get(
                        url, params={"offset": offset}, headers=self.api_auth_header
                    )
                    response.raise_for_status()
                    data = response.json()

                    # Fetch and update on-call user information for services
                    if data_key == "services":
                        service_data = await self.update_oncall_users(data, data_key)
                        all_data.extend(service_data)
                    else:
                        all_data.extend(data[data_key])

                    has_more_data = data["more"]
                    if has_more_data:
                        offset += data["limit"]
                except httpx.HTTPStatusError as e:
                    logger.error(
                        f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
                    )
                    raise

        return all_data

    async def get_singular_from_pager_duty(
        self, object_type: str, identifier: str
    ) -> dict[str, Any]:
        url = f"{self.api_url}/{object_type}/{identifier}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self.api_auth_header)
                response.raise_for_status()
                data = response.json()
                return data
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
                )
                raise

    async def create_webhooks_if_not_exists(self) -> None:
        all_subscriptions = await self.paginate_request_to_pager_duty(
            data_key="webhook_subscriptions"
        )

        invoke_url = f"{self.app_host}/integration/webhook"

        for webhook in all_subscriptions:
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

        async with httpx.AsyncClient() as client:
            try:
                await client.post(
                    f"{self.api_url}/webhook_subscriptions",
                    json=body,
                    headers=self.api_auth_header,
                )
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
                )

    async def get_oncall_user(self, escalation_policy_id: str) -> dict[str, Any]:
        url = f"{self.api_url}/oncalls"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url,
                    params={
                        "escalation_policy_ids[]": escalation_policy_id,
                        "include[]": "users",
                    },
                    headers=self.api_auth_header,
                )
                response.raise_for_status()
                data = response.json()
                return data
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
                )
                raise

    async def update_oncall_users(
        self, data: dict[str, Any], data_key: str
    ) -> list[Any]:
        logger.info("Fetching and matching who is on-call for services")
        escalation_policy_ids = [
            service["escalation_policy"]["id"] for service in data[data_key]
        ]

        oncall_users = await self.get_oncall_user(",".join(escalation_policy_ids))
        all_data = []

        for service in data[data_key]:
            escalation_policy_id = service["escalation_policy"]["id"]

            matching_oncall_user = [
                user
                for user in oncall_users["oncalls"]
                if user["escalation_policy"]["id"] == escalation_policy_id
            ]

            if matching_oncall_user:
                service["oncall_user"] = matching_oncall_user
                all_data.append(service)
        return all_data
