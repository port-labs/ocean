"""Unified CloudTrail live-events webhook processor.

All supported kinds share one processor. Per-kind behavior is delegated to
``cloudtrail_parser`` (event normalization) and ``exporter_bindings`` (fetch
and delete payloads).
"""

from typing import cast

from loguru import logger

from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from integration import AWSResourceConfig
from aws.auth.session_factory import get_session_for_account
from aws.core.helpers.utils import (
    is_access_denied_exception,
    is_resource_not_found_exception,
)
from aws.webhook.cloudtrail_parser import (
    CloudTrailEventAction,
    is_supported_cloudtrail_event,
    parse_cloudtrail_event,
)
from aws.webhook.exporter_bindings import EXPORTER_REGISTRY
from aws.webhook.webhook_processors.base_webhook_processor import BaseWebhookProcessor


class CloudTrailWebhookProcessor(BaseWebhookProcessor):
    """Handles CloudTrail live events for all registered resource kinds."""

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return is_supported_cloudtrail_event(event.payload)

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        parsed = parse_cloudtrail_event(event.payload)
        return [parsed.kind] if parsed is not None else []

    async def validate_payload(self, payload: EventPayload) -> bool:
        return parse_cloudtrail_event(payload) is not None

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        parsed = parse_cloudtrail_event(payload)
        if parsed is None:
            logger.warning("Received an unparsable CloudTrail live event, skipping")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        binding = EXPORTER_REGISTRY.get(parsed.kind)
        if binding is None:
            logger.warning(
                f"No exporter binding for kind {parsed.kind}; skipping live event"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        if parsed.action == CloudTrailEventAction.DELETE:
            logger.info(
                f"Processing {parsed.kind} delete live event: {parsed.identifier}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[
                    {
                        "Type": parsed.kind,
                        "Properties": binding.delete_properties_factory(parsed),
                    }
                ],
            )

        logger.info(
            f"Processing {parsed.kind} {parsed.event_name} live event: "
            f"{parsed.identifier} (account={parsed.account_id}, region={parsed.region})"
        )

        session = await get_session_for_account(parsed.account_id)
        if session is None:
            logger.warning(
                f"No session available for account {parsed.account_id}; "
                f"skipping live event for {parsed.kind} {parsed.identifier}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        include_actions: list[str] = []
        if resource_config is not None:
            include_actions = cast(
                AWSResourceConfig, resource_config
            ).selector.include_actions

        exporter = binding.exporter_cls(session)
        options = binding.request_factory(parsed, include_actions)

        try:
            resource = await exporter.get_resource(options)
        except Exception as error:
            if is_access_denied_exception(error) or is_resource_not_found_exception(
                error
            ):
                logger.warning(
                    f"Could not fetch {parsed.kind} {parsed.identifier} after live "
                    f"event ({error}); treating as deleted"
                )
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[
                        {
                            "Type": parsed.kind,
                            "Properties": binding.delete_properties_factory(parsed),
                        }
                    ],
                )
            raise

        return WebhookEventRawResults(
            updated_raw_results=[resource], deleted_raw_results=[]
        )
