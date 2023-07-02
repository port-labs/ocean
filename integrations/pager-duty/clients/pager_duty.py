from typing import Any, Dict, List

import requests


class PagerDutyClient:
    def __init__(self, token: str, url: str, app_url: str):
        self.token = token
        self.url = url
        self.app_url = app_url

    @property
    def incident_upsert_events(self) -> List[str]:
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
    def service_upsert_events(self) -> List[str]:
        return [
            "service.created",
            "service.updated",
        ]

    @property
    def service_delete_events(self) -> List[str]:
        return [
            "service.deleted",
        ]

    @property
    def all_events(self) -> List[str]:
        return (
            self.incident_upsert_events
            + self.service_upsert_events
            + self.service_delete_events
        )

    def paginate_request_to_pager_duty(
        self, offset=0, data_key: str = "data"
    ) -> List[Any]:
        url = f"{self.url}/{data_key}"

        pager_headers = {"Authorization": f"Token token={self.token}"}

        response = requests.get(url, headers=pager_headers).json()
        data = response[data_key]

        if response["more"]:
            data += self.paginate_request_to_pager_duty(
                offset=offset + response["limit"], data_key=data_key
            )

        return data

    def get_singular_from_pager_duty(
        self, plural: str, singular: str, id: str = "data"
    ) -> List[Any]:
        url = f"{self.url}/{plural}/{id}"

        pager_headers = {"Authorization": f"Token token={self.token}"}

        response = requests.get(url, headers=pager_headers).json()
        data = response[singular]

        return data

    def create_webhooks_if_not_exists(self):
        pager_headers = {"Authorization": f"Token token={self.token}"}

        webhooks_subscription = self.paginate_request_to_pager_duty(
            data_key="webhook_subscriptions"
        )

        invoke_url = f"{self.app_url}/integration/webhook"

        for webhook in webhooks_subscription:
            if webhook["delivery_method"]["url"] == invoke_url:
                return

        body = {
            "webhook_subscription": {
                "delivery_method": {
                    "type": "http_delivery_method",
                    "url": invoke_url,
                },
                "description": "Port Ocean integration",
                "events": self.all_events,
                "filter": {"type": "account_reference"},
                "type": "webhook_subscription",
            }
        }

        requests.post(
            f"{self.url}/webhook_subscriptions",
            json=body,
            headers=pager_headers,
        )
