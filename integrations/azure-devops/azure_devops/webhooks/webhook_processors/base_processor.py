import base64
from abc import abstractmethod
from typing import Dict

from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEventRawResults,
)

from azure_devops.client.azure_devops_client import AzureDevopsClient
from azure_devops.client.client_manager import AzureDevopsClientManager
from azure_devops.misc import extract_org_name_from_url


class AzureDevOpsBaseWebhookProcessor(AbstractWebhookProcessor):
    async def authenticate(
        self, payload: EventPayload, headers: Dict[str, str]
    ) -> bool:
        authorization = headers.get("authorization")
        webhook_secret = ocean.integration_config.get("webhook_secret")

        if authorization:
            try:
                auth_type, encoded_token = authorization.split(" ", 1)
                if auth_type.lower() != "basic":
                    return False

                decoded = base64.b64decode(encoded_token).decode("utf-8")
                _, token = decoded.split(":", 1)
                return token == webhook_secret
            except (ValueError, UnicodeDecodeError):
                return False
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Base payload validation"""
        required_fields = ["eventType", "publisherId", "resource"]
        return all(field in payload for field in required_fields)

    @staticmethod
    def _extract_org_url_from_payload(payload: EventPayload) -> str | None:
        """Extract the source organization URL from a webhook payload"""
        containers = payload.get("resourceContainers") or {}
        for key in ("account", "collection"):
            container = containers.get(key) or {}
            base_url = container.get("baseUrl")
            if base_url:
                return str(base_url).rstrip("/")
        return None

    def _get_client_for_webhook(self, payload: EventPayload) -> AzureDevopsClient:
        """Resolve the per-org Azure DevOps client for a webhook event"""
        manager = AzureDevopsClientManager.create_from_ocean_config()
        org_url = self._extract_org_url_from_payload(payload)
        if org_url and manager.get_client_for_org(org_url) is None:
            logger.warning(
                f"Webhook event references unknown organization {org_url}; "
                f"falling back to first configured client. "
                f"Check organizationUrls / organizationUrl config."
            )
        return manager.get_client_for_org_or_first(org_url)

    def _enrich_webhook_results(
        self,
        result: WebhookEventRawResults,
        payload: EventPayload,
    ) -> None:
        org_url = self._extract_org_url_from_payload(payload)
        if not org_url:
            return
        org_name = extract_org_name_from_url(org_url)
        for entity in result.updated_raw_results:
            entity["__organizationUrl"] = org_url
            entity["__organizationName"] = org_name
        for entity in result.deleted_raw_results:
            entity["__organizationUrl"] = org_url
            entity["__organizationName"] = org_name

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        result = await self._handle_webhook_event(payload, resource_config)
        self._enrich_webhook_results(result, payload)
        return result

    @abstractmethod
    async def _handle_webhook_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults: ...
