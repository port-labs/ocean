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
from azure_devops.webhooks import subscription_registry

# --- Authentication constants ---
AUTHORIZATION_HEADER = "authorization"
AUTH_TYPE_BASIC = "basic"
WEBHOOK_SECRET_CONFIG_KEY = "webhook_secret"

# --- Payload structure constants ---
REQUIRED_PAYLOAD_FIELDS = ("eventType", "publisherId", "resource")
SUBSCRIPTION_ID_FIELD = "subscriptionId"


# =============================================================================
# Module-level helpers
# =============================================================================


def _enrich_items(
    items: list[dict[str, Any]], org_url: str, org_name: str
) -> list[dict[str, Any]]:
    """Stamp organization metadata onto each raw entity dict."""
    return [
        {**item, ORG_URL_FIELD: org_url, ORG_NAME_FIELD: org_name} for item in items
    ]


# =============================================================================
# Base processor
# =============================================================================


class AzureDevOpsBaseWebhookProcessor(AbstractWebhookProcessor):
    _resolved_client: Optional[AzureDevopsClient] = None

    # -------------------------------------------------------------------------
    # Authentication
    # -------------------------------------------------------------------------

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

    # -------------------------------------------------------------------------
    # Client resolution via subscription registry
    # -------------------------------------------------------------------------

    def _resolve_client(self, payload: EventPayload) -> Optional[AzureDevopsClient]:
        """Look up the client for this event using the subscription registry.

        Resolution order:
          1. Look up payload["subscriptionId"] in the subscription registry
          2. If not found and only one client is configured, use that one
          3. Otherwise return None (no client available)

        When the registry is empty (ONCE mode / resync / tests), step 1 is
        skipped and we go directly to the single-client fallback.
        """
        sub_id = payload.get(SUBSCRIPTION_ID_FIELD)
        if sub_id and subscription_registry.size() > 0:
            client = subscription_registry.get_client(sub_id)
            if client:
                return client

        # Fallback: when the registry can't resolve (e.g. test notifications with
        # zeroed-out subscription IDs, ONCE mode where no webhooks are created, or
        # subscriptions that pre-date the registry), use the single configured client.
        manager = AzureDevopsClientManager.create_from_ocean_config()
        clients = manager.get_clients()
        if len(clients) == 1:
            return clients[0]

        # Multi-org with unresolved subscription — caller must handle None.
        return None

    def _get_client_for_webhook(self, payload: EventPayload) -> AzureDevopsClient:
        """Return the client resolved by handle_event for this request.

        Only call this from _handle_webhook_event where the client is
        guaranteed to exist (handle_event already confirmed it).
        """
        if self._resolved_client is not None:
            return self._resolved_client
        client = self._resolve_client(payload)
        if client is None:
            raise ValueError(
                "No client available for this webhook event. "
                "This should have been caught in handle_event."
            )
        return client

    # -------------------------------------------------------------------------
    # Event handling (main entry point)
    # -------------------------------------------------------------------------

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Route a webhook event to the appropriate handler.

        Resolution:
          1. Look up the client via subscription registry (or single-client default)
          2. If client found: full processing with API calls
          3. If no client: best-effort processing with raw payload only
        """
        client = self._resolve_client(payload)
        # Cache so sub-processors can access via _get_client_for_webhook()
        # without re-resolving.
        self._resolved_client = client

        if client:
            org_url = client._organization_base_url
            org_name = extract_org_name_from_url(org_url)
            results = await self._handle_webhook_event(payload, resource_config)
        else:
            logger.warning(
                f"No client found for subscription '{payload.get(SUBSCRIPTION_ID_FIELD)}' "
                "— processing without API enrichment"
            )
            org_url = ""
            org_name = ""
            results = await self._handle_webhook_event_no_client(
                payload, resource_config
            )

        return self._enrich_webhook_results(results, org_url, org_name)

    # -------------------------------------------------------------------------
    # Enrichment
    # -------------------------------------------------------------------------

    def _enrich_webhook_results(
        self,
        results: WebhookEventRawResults,
        org_url: str,
        org_name: str,
    ) -> WebhookEventRawResults:
        """Stamp __organizationUrl and __organizationName onto all results."""
        if not org_url:
            return results
        return WebhookEventRawResults(
            updated_raw_results=_enrich_items(
                results.updated_raw_results, org_url, org_name
            ),
            deleted_raw_results=_enrich_items(
                results.deleted_raw_results, org_url, org_name
            ),
        )

    # -------------------------------------------------------------------------
    # Subclass hooks
    # -------------------------------------------------------------------------

    @abstractmethod
    async def _handle_webhook_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Process the event with full API access (client is available)."""
        ...

    async def _handle_webhook_event_no_client(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Fallback: process the event without a client (no API calls).

        Returns the raw resource from the payload as-is. Subclasses may
        override this for event-specific logic that doesn't need a client.
        """
        resource = payload.get("resource", {})
        return WebhookEventRawResults(
            updated_raw_results=[resource],
            deleted_raw_results=[],
        )
