import base64
from abc import abstractmethod
from typing import Dict, Optional

from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEventRawResults,
)

from azure_devops.client.client_manager import AzureDevopsClientManager
from azure_devops.misc import ORG_NAME_FIELD, ORG_URL_FIELD, extract_org_name_from_url


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

    def _extract_org_url_from_payload(self, payload: EventPayload) -> Optional[str]:
        """Extract the organization base URL from a webhook payload.

        Reads ``resourceContainers.account.baseUrl`` with
        ``resourceContainers.collection.baseUrl`` as fallback.
        """
        containers = payload.get("resourceContainers", {})
        url = (
            containers.get("account", {}).get("baseUrl")
            or containers.get("collection", {}).get("baseUrl")
        )
        return url.rstrip("/") if url else None

    def _get_client_for_webhook(self, payload: EventPayload):
        """Resolve the per-org AzureDevopsClient for a webhook payload."""
        manager = AzureDevopsClientManager.create_from_ocean_config()
        org_url = self._extract_org_url_from_payload(payload)
        return manager.get_client_for_org_or_first(org_url)

    def _enrich_webhook_results(
        self,
        results: WebhookEventRawResults,
        payload: EventPayload,
    ) -> WebhookEventRawResults:
        """Annotate updated/deleted raw results with __organizationUrl/Name."""
        org_url = self._extract_org_url_from_payload(payload)
        if not org_url:
            return results

        org_name = extract_org_name_from_url(org_url)

        def _enrich(items: list) -> list:
            return [
                {**item, ORG_URL_FIELD: org_url, ORG_NAME_FIELD: org_name}
                for item in items
            ]

        return WebhookEventRawResults(
            updated_raw_results=_enrich(results.updated_raw_results),
            deleted_raw_results=_enrich(results.deleted_raw_results),
        )

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        results = await self._handle_webhook_event(payload, resource_config)
        return self._enrich_webhook_results(results, payload)

    @abstractmethod
    async def _handle_webhook_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Subclasses implement their event handling here."""
        ...
