import base64
from abc import abstractmethod
from typing import Any, Dict, Optional

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
from azure_devops.misc import ORG_NAME_FIELD, ORG_URL_FIELD, extract_org_name_from_url

AUTHORIZATION_HEADER = "authorization"
AUTH_TYPE_BASIC = "basic"
WEBHOOK_SECRET_CONFIG_KEY = "webhook_secret"
REQUIRED_PAYLOAD_FIELDS = ("eventType", "publisherId", "resource")
RESOURCE_CONTAINERS_KEY = "resourceContainers"
ACCOUNT_BASE_URL_PATH = ("account", "baseUrl")
COLLECTION_BASE_URL_PATH = ("collection", "baseUrl")
ORG_URL_QUERY_PARAM = "org"
ORIGINAL_REQUEST_ATTR = "_original_request"


def _enrich_items(
    items: list[dict[str, Any]], org_url: str, org_name: str
) -> list[dict[str, Any]]:
    return [
        {**item, ORG_URL_FIELD: org_url, ORG_NAME_FIELD: org_name} for item in items
    ]


class AzureDevOpsBaseWebhookProcessor(AbstractWebhookProcessor):
    async def authenticate(
        self, payload: EventPayload, headers: Dict[str, str]
    ) -> bool:
        authorization = headers.get(AUTHORIZATION_HEADER)
        if not authorization:
            return True

        try:
            auth_type, encoded_token = authorization.split(" ", 1)
            if auth_type.lower() != AUTH_TYPE_BASIC:
                return False
            decoded = base64.b64decode(encoded_token).decode("utf-8")
            _, token = decoded.split(":", 1)
        except (ValueError, UnicodeDecodeError):
            return False
        webhook_secret = ocean.integration_config.get(WEBHOOK_SECRET_CONFIG_KEY)
        return token == webhook_secret

    async def validate_payload(self, payload: EventPayload) -> bool:
        return all(field in payload for field in REQUIRED_PAYLOAD_FIELDS)

    def _extract_org_url_from_payload(self, payload: EventPayload) -> Optional[str]:
        """Extract the organization base URL from a webhook payload.

        Primary source: ``resourceContainers.account.baseUrl`` (or
        ``collection.baseUrl`` as a TFS/on-premise fallback).

        Secondary source: the ``?org=`` query parameter embedded in the
        webhook endpoint URL at registration time.  Some ADO event types
        (e.g. Advanced Security alerts) omit ``baseUrl`` from
        ``resourceContainers``, so the query param is the only reliable
        signal for those events.
        """
        containers = payload.get(RESOURCE_CONTAINERS_KEY, {})
        account_key, base_url_key = ACCOUNT_BASE_URL_PATH
        collection_key, _ = COLLECTION_BASE_URL_PATH
        url = containers.get(account_key, {}).get(base_url_key) or containers.get(
            collection_key, {}
        ).get(base_url_key)

        if not url:
            request = getattr(self.event, ORIGINAL_REQUEST_ATTR, None)
            if request is not None:
                url = request.query_params.get(ORG_URL_QUERY_PARAM)

        return url.rstrip("/") if url else None

    def _get_client_for_webhook(self, payload: EventPayload) -> AzureDevopsClient:
        """Resolve the per-org AzureDevopsClient for a webhook payload.

        Only call this after ``handle_event`` has already validated that the
        org URL is present and a matching client exists.
        """
        manager = AzureDevopsClientManager.create_from_ocean_config()
        org_url = self._extract_org_url_from_payload(payload)
        client = manager.get_client_for_org(org_url or "")
        if client is None:
            raise ValueError(
                f"No configured client for org '{org_url}'. "
                "This should have been caught in handle_event."
            )
        return client

    def _enrich_webhook_results(
        self,
        results: WebhookEventRawResults,
        org_url: str,
        org_name: str,
    ) -> WebhookEventRawResults:
        """Annotate updated/deleted raw results with __organizationUrl/Name."""
        return WebhookEventRawResults(
            updated_raw_results=_enrich_items(
                results.updated_raw_results, org_url, org_name
            ),
            deleted_raw_results=_enrich_items(
                results.deleted_raw_results, org_url, org_name
            ),
        )

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        empty = WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        org_url = self._extract_org_url_from_payload(payload)
        if not org_url:
            logger.warning(
                "Dropping webhook event: organization URL not found in payload"
            )
            return empty

        manager = AzureDevopsClientManager.create_from_ocean_config()
        if not manager.get_client_for_org(org_url):
            logger.warning(
                f"Dropping webhook event: no configured client for org '{org_url}'"
            )
            return empty

        org_name = extract_org_name_from_url(org_url)
        results = await self._handle_webhook_event(payload, resource_config)
        return self._enrich_webhook_results(results, org_url, org_name)

    @abstractmethod
    async def _handle_webhook_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Subclasses implement their event handling here."""
        ...
