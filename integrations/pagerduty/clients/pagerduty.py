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

    async def paginate_request_to_pager_duty(
        self, offset: int = 0, data_key: str = "data"
    ) -> list[Any]:
        url = f"{self.api_url}/{data_key}"

        all_data = []

        while True:
            params = {"offset": offset}
            async with httpx.AsyncClient() as client:
                try:
                    logger.info(f"Fetching resource: {data_key}")
                    response = await client.get(
                        url, headers=self.api_auth_header, params=params
                    )
                    response.raise_for_status()  # Raise an exception for 4xx/5xx status codes
                    data = response.json()
                    all_data.extend(data[data_key])

                    if not data["more"]:
                        break

                    offset += data["limit"]
                except httpx.RequestError as e:
                    logger.info(
                        f"An error occurred while fetching resource: {data_key} error: {e}"
                    )
                    break

        return all_data

    async def get_singular_from_pager_duty(
        self, plural: str, singular: str, id: str = "data"
    ) -> dict[str, Any]:
        url = f"{self.api_url}/{plural}/{id}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self.api_auth_header)
                response.raise_for_status()  # Raise an exception for 4xx/5xx status codes
                data = response.json()
                return data[singular]
            except httpx.RequestError as e:
                logger.info(
                    f"An error occurred while fetching resource: {plural} error: {e}"
                )
                return {}

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
            except httpx.RequestError as e:
                logger.info(
                    f"An error occurred while subscribing to integration webhook: {e}"
                )
