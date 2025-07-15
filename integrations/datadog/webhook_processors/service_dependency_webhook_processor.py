import base64
from typing import Any

from initialize_client import init_client
from integration import ObjectKind
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from loguru import logger


class ServiceDependencyWebhookProcessor(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        """Only process events that are related to service dependencies."""
        payload = event.payload
        event_type = payload.get("event_type", "")

        # Event types that may indicate changes in service behavior or dependencies
        service_related_events = [
            "service_check",
            "query_alert_monitor",
            "metric_slo_alert",
            "monitor_slo_alert",
            "outlier_monitor",
            "event_v2_alert",
        ]

        should_process = event_type in service_related_events

        logger.info(
            f"Service dependency webhook processor: event_type={event_type}, should_process={should_process}"
        )
        return should_process

    async def get_matching_kinds(self, _: WebhookEvent) -> list[str]:
        return [ObjectKind.SERVICE_DEPENDENCY]

    async def handle_event(
        self, payload: EventPayload, _: ResourceConfig
    ) -> WebhookEventRawResults:
        """Handle service dependency webhook events."""
        try:
            service_id = payload.get("service_id")

            if service_id:
                logger.info(
                    f"Processing service dependency webhook for service: {service_id}"
                )
                dd_client = init_client()
                service_dependency = await dd_client.get_single_service_dependency(
                    service_id
                )

                if service_dependency:
                    logger.info(
                        f"Successfully fetched service dependency for {service_id}"
                    )
                    return WebhookEventRawResults(
                        updated_raw_results=[service_dependency], deleted_raw_results=[]
                    )

            logger.warning(f"No service ID found in webhook payload: {payload}")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        except Exception as e:
            logger.error(
                f"Error processing service dependency webhook: {str(e)}", exc_info=True
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

    async def authenticate(
        self, payload: EventPayload, headers: dict[str, Any]
    ) -> bool:
        authorization = headers.get("authorization")
        webhook_secret = ocean.integration_config.get("webhook_secret")

        if not webhook_secret:
            return True  # No authentication required if no secret is configured

        if not authorization:
            logger.warning("No authorization header found in webhook request")
            return False

        try:
            auth_type, encoded_token = authorization.split(" ", 1)
            if auth_type.lower() != "basic":
                logger.warning(f"Invalid authorization type: {auth_type}")
                return False

            decoded = base64.b64decode(encoded_token).decode("utf-8")
            _, token = decoded.split(":", 1)
            is_valid = token == webhook_secret

            if not is_valid:
                logger.warning("Invalid webhook secret")

            return is_valid
        except (ValueError, UnicodeDecodeError) as e:
            logger.warning(f"Error decoding authorization header: {str(e)}")
            return False

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate that the payload contains required fields for service dependency events."""
        has_service_info = any(key in payload for key in ["service_id"])
        has_event_info = "event_type" in payload

        is_valid = has_service_info and has_event_info

        if not is_valid:
            logger.warning(f"Invalid webhook payload for service dependency: {payload}")

        return is_valid
