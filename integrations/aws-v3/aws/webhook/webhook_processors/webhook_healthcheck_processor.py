"""Smoke-test processor for the AWS-V3 live-events endpoint.

EventBridge has no native "ping" concept (unlike GitHub), so we expose an
explicit healthcheck path: a request that carries `X-Port-Healthcheck: 1`
is treated as a synthetic poke from an operator (`curl`, the deployment
pipeline, etc.), short-circuited to an empty result, and never matched by
the EC2/ECS/Lambda/S3 processors.

The processor still goes through the standard auth + validation pipeline,
so a successful healthcheck proves the bearer token is configured
correctly end-to-end.
"""

from __future__ import annotations

from loguru import logger

from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)


HEALTHCHECK_HEADER = "x-port-healthcheck"


class WebhookHealthcheckProcessor(AbstractWebhookProcessor):
    """Acknowledges manual healthcheck pokes without touching any AWS API.

    Distinct from `_AwsAbstractWebhookProcessor` because:
      - It must accept a non-EventBridge payload shape.
      - It needs to be matched FIRST in the registry so it short-circuits
        before the kind-specific processors look at the event.
      - Its only auth gate is the integration's `webhook_secret`, which
        the path-scoped middleware already verified.
    """

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        return True

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return event.headers.get(HEALTHCHECK_HEADER) == "1"

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        logger.info(
            "AWS-V3 live-events healthcheck received; returning empty kind list"
        )
        return []

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])
