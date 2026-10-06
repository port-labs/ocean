from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    EventPayload,
    EventHeaders,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventRawResults
from loguru import logger
from integration import ApplicationResourceConfig
from misc import ResourceKindsWithSpecialHandling, init_client
from typing import cast, Dict, Any


class ArgocdApplicationWebhookProcessor(AbstractWebhookProcessor):
    """Handles ArgoCD notification webhooks for application upsert events."""

    _ACTION = "upsert"

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ResourceKindsWithSpecialHandling.APPLICATION]

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        return bool(payload.get("application_name"))

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return event.payload.get("action") == self._ACTION

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        argocd_client = init_client()
        application_name = payload["application_name"]
        namespace = payload.get("application_namespace")
        query_params = self._resolve_query_params(resource_config, namespace)
        if query_params is None:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        logger.info(f"Processing webhook upsert for application: {application_name}")
        application = await argocd_client.get_application_by_name(
            application_name,
            params=query_params,
        )

        if not application:
            logger.warning(
                f"Application {application_name} not found, skipping webhook processing"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        logger.info(f"Application {application_name} found, registering raw data")

        return WebhookEventRawResults(
            updated_raw_results=[application],
            deleted_raw_results=[],
        )

    def _resolve_query_params(
        self, resource_config: ResourceConfig, namespace: str | None
    ) -> Dict[str, Any] | None:
        """
        If a namespace is explicitly provided in the webhook payload ("application_namespace"),
        respect it for downstream queries. However, it's possible that the user's
        application selector in the config has already specified a namespace filter (in query_params["appNamespace"]).
        1. If query_params already has an "appNamespace" filter:
            - If it does *not* match the webhook's namespace, we must *not* process this webhook, as the event namespace
            is not included in the filter the user configured. We log this mismatch and gracefully exit.
        2. Otherwise, inject the webhook's namespace into query_params, so queries downstream know
            exactly which namespace to search in (even if the original selector was unset or non-restrictive).
        """
        selector = cast(ApplicationResourceConfig, resource_config).selector
        query_params = (
            selector.query_params.generate_request_params
            if selector.query_params
            else {}
        )
        if namespace:
            if query_params and query_params.get("appNamespace"):
                if query_params["appNamespace"] != namespace:
                    logger.info(
                        f"Namespace {namespace} does not match filtered by selector {query_params}, skipping webhook processing"
                    )
                    return None
            # At this point, either there was no appNamespace filter, or it matches the webhook.
            # We set appNamespace to the incoming value to scope queries as tightly as possible.
            query_params["appNamespace"] = namespace
        return query_params
