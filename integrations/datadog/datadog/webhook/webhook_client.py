import json
import uuid
from typing import Any, Iterable

import httpx
from loguru import logger

from datadog.client import DatadogClient

MONITOR_WEBHOOK_PATH = "/webhook/monitor-events"
AUDIT_TRAIL_WEBHOOK_PATH = "/webhook/audit-trail"
DEFAULT_NOTIFICATION_RULE_SCOPE = "service:*"

_PORT_MONITOR_NOTIFICATION_RULE_PREFIX = "Port Ocean Monitor Events"
PORT_AUTH_HEADER_NAME = "X-Port-Ocean-Webhook-Secret"

_WEBHOOK_PAYLOAD_TEMPLATE: dict[str, str] = {
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
}


class DatadogWebhookClient:
    def __init__(self, clients: Iterable[DatadogClient]):
        self.clients = clients

    async def upsert_webhook_setup(
        self,
        base_url: str,
        webhook_secret: str | None,
        org_id: str,
        integration_identifier: str,
        notification_rule_scope: str | None = None,
    ) -> None:
        webhook_name = self._build_webhook_name(org_id, integration_identifier)
        webhook_target = self._build_webhook_target_url(
            base_url, f"/integration{MONITOR_WEBHOOK_PATH}"
        )
        for client in self.clients:
            try:
                await self._sync_webhook(
                    client, webhook_name, webhook_target, webhook_secret
                )
                await self._sync_notification_rule(
                    client,
                    webhook_name,
                    notification_rule_scope=notification_rule_scope
                    or DEFAULT_NOTIFICATION_RULE_SCOPE,
                )
            except Exception as e:
                logger.error(
                    f"Failed to setup Datadog live events for org "
                    f"'{client.org_id}': {str(e)}, skipping..."
                )
                continue

    async def _sync_webhook(
        self,
        client: DatadogClient,
        webhook_name: str,
        target_url: str,
        webhook_secret: str | None,
    ) -> None:
        webhooks_base = (
            f"{client.api_url}/api/v1/integration/webhooks/configuration/webhooks"
        )
        existing = await self._find_existing_webhook(client, webhook_name)
        desired_body = self._build_webhook_body(
            target_url, webhook_secret, name=webhook_name
        )

        if existing is None:
            logger.info(f"Creating Datadog webhook '{webhook_name}'")
            await client.send_api_request(
                url=webhooks_base, method="POST", json_data=desired_body
            )
            return

        if not self._webhook_needs_update(existing, target_url, webhook_secret):
            logger.info(f"Datadog webhook '{webhook_name}' is up to date")
            return

        logger.info(f"Updating Datadog webhook '{webhook_name}'")
        update_body = self._build_webhook_body(target_url, webhook_secret)
        await client.send_api_request(
            url=f"{webhooks_base}/{webhook_name}", method="PUT", json_data=update_body
        )

    async def _find_existing_webhook(
        self, client: DatadogClient, webhook_name: str
    ) -> dict[str, Any] | None:
        url = (
            f"{client.api_url}/api/v1/integration/webhooks/configuration/webhooks"
            f"/{webhook_name}"
        )
        try:
            response = await client.send_api_request(url=url)
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
        existing_payload = existing.get("payload")
        try:
            parsed_payload = json.loads(existing_payload) if existing_payload else None
        except (json.JSONDecodeError, TypeError):
            parsed_payload = None
        return (
            existing.get("url") != target_url
            or existing.get("custom_headers") != expected_headers
            or parsed_payload != _WEBHOOK_PAYLOAD_TEMPLATE
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
            "payload": json.dumps(_WEBHOOK_PAYLOAD_TEMPLATE),
        }
        if name:
            body["name"] = name
        if webhook_secret:
            body["custom_headers"] = json.dumps({PORT_AUTH_HEADER_NAME: webhook_secret})
        return body

    async def _sync_notification_rule(
        self,
        client: DatadogClient,
        webhook_name: str,
        notification_rule_scope: str,
    ) -> None:
        rules_url = f"{client.api_url}/api/v2/monitor/notification_rule"
        recipient = f"webhook-{webhook_name}"

        rules_response = await client.send_api_request(url=rules_url)
        existing_rule = self._find_rule_by_scope_and_prefix(
            rules_response,
            scope=notification_rule_scope,
            name_prefix=_PORT_MONITOR_NOTIFICATION_RULE_PREFIX,
        )

        if existing_rule is None:
            rule_name = (
                f"{_PORT_MONITOR_NOTIFICATION_RULE_PREFIX}-{uuid.uuid4().hex[:8]}"
            )
            logger.info(
                f"Creating monitor notification rule '{rule_name}' with scope '{notification_rule_scope}'"
            )
            await client.send_api_request(
                url=rules_url,
                method="POST",
                json_data=self._build_notification_rule_payload(
                    rule_name,
                    [recipient],
                    scope=notification_rule_scope,
                ),
            )
            return

        attributes = existing_rule.get("attributes", {})
        current_recipients: list[str] = attributes.get("recipients", [])

        if recipient in current_recipients:
            logger.debug("Monitor notification rule is already up to date")
            return

        rule_id = existing_rule.get("id")
        rule_name = attributes.get("name")
        updated_recipients = [*current_recipients, recipient]
        logger.info(f"Appending recipient to monitor notification rule '{rule_id}'")
        await client.send_api_request(
            url=f"{rules_url}/{rule_id}",
            method="PATCH",
            json_data=self._build_notification_rule_payload(
                rule_name,
                updated_recipients,
                rule_id=rule_id,
                scope=notification_rule_scope,
            ),
        )

    @staticmethod
    def _build_notification_rule_payload(
        name: str,
        recipients: list[str],
        scope: str,
        rule_id: str | None = None,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {
            "type": "monitor-notification-rule",
            "attributes": {
                "name": name,
                "filter": {"scope": scope},
                "recipients": recipients,
            },
        }
        if rule_id:
            data["id"] = rule_id
        return {"data": data}

    @staticmethod
    def _find_rule_by_scope_and_prefix(
        response: dict[str, Any], scope: str, name_prefix: str
    ) -> dict[str, Any] | None:
        """Return the first notification rule whose name starts with *name_prefix*
        and whose filter scope matches *scope* exactly.

        Datadog rejects creating a rule with a scope that already exists, so we
        must locate an existing rule by scope (not just by name) and append our
        webhook recipient to it instead of creating a duplicate.
        """
        for rule in response.get("data", []):
            attrs = rule.get("attributes", {})
            if (
                attrs.get("name", "").startswith(name_prefix)
                and attrs.get("filter", {}).get("scope") == scope
            ):
                return rule
        return None

    @staticmethod
    def _build_webhook_target_url(base_url: str, path: str) -> str:
        return f"{base_url.rstrip('/')}/{path.lstrip('/')}"

    @staticmethod
    def _build_webhook_name(org_id: str, integration_identifier: str) -> str:
        return f"{org_id}-{integration_identifier}"
