import json
from typing import Any

import httpx
from loguru import logger

from datadog.client import DatadogClient

MONITOR_WEBHOOK_PATH = "/webhook/monitor-events"
AUDIT_TRAIL_WEBHOOK_PATH = "/webhook/audit-trail"

_PORT_MONITOR_NOTIFICATION_RULE_NAME = "Port Ocean Monitor Events"
PORT_AUTH_HEADER_NAME = "X-Port-Ocean-Webhook-Secret"

_WEBHOOK_PAYLOAD_TEMPLATE = json.dumps(
    {
        "id": "$ID",
        "message": "$TEXT_ONLY_MSG",
        "priority": "$PRIORITY",
        "last_updated": "$LAST_UPDATED",
        "event_type": "$EVENT_TYPE",
        "event_url": "$LINK",
        "service": "$HOSTNAME",
        "service_id": "$SERVICE_ID",
        "service_name": "$SERVICE_NAME",
        "creator": "$USER",
        "title": "$EVENT_TITLE",
        "date": "$DATE",
        "org_id": "$ORG_ID",
        "org_name": "$ORG_NAME",
        "alert_id": "$ALERT_ID",
        "alert_metric": "$ALERT_METRIC",
        "alert_status": "$ALERT_STATUS",
        "alert_title": "$ALERT_TITLE",
        "alert_type": "$ALERT_TYPE",
        "tags": "$TAGS",
        "body": "$EVENT_MSG",
    },
    indent=4,
)


class DatadogWebhookClient:
    def __init__(self, client: DatadogClient):
        self.client = client

    async def upsert_webhook_setup(
        self,
        base_url: str,
        webhook_secret: str | None,
        org_id: str,
        integration_identifier: str,
        notification_rule_tags: list[str],
    ) -> None:
        webhook_name = self._build_webhook_name(org_id, integration_identifier)
        webhook_target = self._build_webhook_target_url(
            base_url, f"/integration{MONITOR_WEBHOOK_PATH}"
        )
        try:
            await self._sync_webhook(webhook_name, webhook_target, webhook_secret)
            await self._sync_notification_rule(
                webhook_name,
                notification_rule_tags=notification_rule_tags,
            )
        except Exception as e:
            logger.error(f"Failed to setup Datadog live events: {str(e)}, skipping...")

    async def _sync_webhook(
        self, webhook_name: str, target_url: str, webhook_secret: str | None
    ) -> None:
        webhooks_base = (
            f"{self.client.api_url}/api/v1/integration/webhooks/configuration/webhooks"
        )
        existing = await self._find_existing_webhook(webhook_name)
        desired_body = self._build_webhook_body(
            target_url, webhook_secret, name=webhook_name
        )

        if existing is None:
            logger.info(f"Creating Datadog webhook '{webhook_name}'")
            await self.client.send_api_request(
                url=webhooks_base, method="POST", json_data=desired_body
            )
            return

        if not self._webhook_needs_update(existing, target_url, webhook_secret):
            logger.info(f"Datadog webhook '{webhook_name}' is up to date")
            return

        logger.info(f"Updating Datadog webhook '{webhook_name}'")
        update_body = self._build_webhook_body(target_url, webhook_secret)
        await self.client.send_api_request(
            url=f"{webhooks_base}/{webhook_name}", method="PUT", json_data=update_body
        )

    async def _find_existing_webhook(self, webhook_name: str) -> dict[str, Any] | None:
        url = (
            f"{self.client.api_url}/api/v1/integration/webhooks/configuration/webhooks"
            f"/{webhook_name}"
        )
        try:
            response = await self.client.send_api_request(url=url)
        except httpx.HTTPStatusError as err:
            if err.response.status_code == 404:
                return None
            raise
        return response if isinstance(response, dict) else None

    @staticmethod
    def _webhook_needs_update(
        existing: dict[str, Any],
        target_url: str,
        webhook_secret: str | None,
    ) -> bool:
        expected_headers = (
            json.dumps({PORT_AUTH_HEADER_NAME: webhook_secret})
            if webhook_secret
            else None
        )
        return (
            existing.get("url") != target_url
            or existing.get("custom_headers") != expected_headers
            or existing.get("payload") != _WEBHOOK_PAYLOAD_TEMPLATE
        )

    @staticmethod
    def _build_webhook_body(
        target_url: str,
        webhook_secret: str | None,
        name: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "url": target_url,
            "encode_as": "json",
            "payload": _WEBHOOK_PAYLOAD_TEMPLATE,
        }
        if name:
            body["name"] = name
        if webhook_secret:
            body["custom_headers"] = json.dumps({PORT_AUTH_HEADER_NAME: webhook_secret})
        return body

    async def _sync_notification_rule(
        self,
        webhook_name: str,
        notification_rule_tags: list[str],
    ) -> None:
        rules_url = f"{self.client.api_url}/api/v2/monitor/notification_rule"
        recipient = f"webhook-{webhook_name}"

        rules_response = await self.client.send_api_request(url=rules_url)
        existing_rule = self._find_rule_by_name(
            rules_response, _PORT_MONITOR_NOTIFICATION_RULE_NAME
        )

        if existing_rule is None:
            logger.info("Creating monitor notification rule")
            await self.client.send_api_request(
                url=rules_url,
                method="POST",
                json_data=self._build_notification_rule_payload(
                    _PORT_MONITOR_NOTIFICATION_RULE_NAME,
                    [recipient],
                    tags=notification_rule_tags,
                ),
            )
            return

        attributes = existing_rule.get("attributes", {})
        current_recipients: list[str] = attributes.get("recipients", [])
        current_tags: list[str] = attributes.get("filter", {}).get("tags", [])

        recipient_up_to_date = recipient in current_recipients
        tags_up_to_date = sorted(current_tags) == sorted(notification_rule_tags)

        if recipient_up_to_date and tags_up_to_date:
            logger.debug("Monitor notification rule is already up to date")
            return

        rule_id = existing_rule.get("id")
        updated_recipients = (
            current_recipients
            if recipient_up_to_date
            else [*current_recipients, recipient]
        )
        logger.info(
            f"Updating monitor notification rule '{rule_id}' "
            f"(recipient_added={not recipient_up_to_date}, tags_changed={not tags_up_to_date})"
        )
        await self.client.send_api_request(
            url=f"{rules_url}/{rule_id}",
            method="PATCH",
            json_data=self._build_notification_rule_payload(
                _PORT_MONITOR_NOTIFICATION_RULE_NAME,
                updated_recipients,
                rule_id=rule_id,
                tags=notification_rule_tags,
            ),
        )

    @staticmethod
    def _build_notification_rule_payload(
        name: str,
        recipients: list[str],
        tags: list[str],
        rule_id: str | None = None,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {
            "type": "monitor-notification-rule",
            "attributes": {
                "name": name,
                "filter": {"tags": tags},
                "recipients": recipients,
            },
        }
        if rule_id:
            data["id"] = rule_id
        return {"data": data}

    @staticmethod
    def _find_rule_by_name(
        response: dict[str, Any], rule_name: str
    ) -> dict[str, Any] | None:
        for rule in response.get("data", []):
            if rule.get("attributes", {}).get("name") == rule_name:
                return rule
        return None

    @staticmethod
    def _build_webhook_target_url(base_url: str, path: str) -> str:
        return f"{base_url.rstrip('/')}/{path.lstrip('/')}"

    @staticmethod
    def _build_webhook_name(org_id: str, integration_identifier: str) -> str:
        return f"{org_id}-{integration_identifier}"
