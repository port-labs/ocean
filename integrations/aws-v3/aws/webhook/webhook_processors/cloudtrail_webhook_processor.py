"""Unified CloudTrail live-events webhook processor.

All supported kinds share one processor. Per-kind behavior is delegated to
``cloudtrail_parser`` (event normalization) and ``kind_to_export_metadata``
(fetch and delete payloads).
"""

from typing import Any, cast

from loguru import logger
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

from integration import AWSResourceConfig
from aws.auth.session_factory import get_session_for_account
from aws.core.exporters.exporter_metadata import (
    LiveEventContext,
    kind_to_export_metadata,
)
from aws.core.helpers.types import ObjectKind
from aws.core.helpers.utils import (
    is_access_denied_exception,
    is_resource_not_found_exception,
)
from aws.webhook.cloudtrail_parser import (
    CloudTrailEventAction,
    is_supported_cloudtrail_event,
    parse_cloudtrail_event,
)
from aws.webhook.consts import LIVE_EVENTS_API_KEY_HEADER
from aws.webhook.feature_flags import is_aws_v3_live_events_enabled


class CloudTrailWebhookProcessor(AbstractWebhookProcessor):
    """Handles CloudTrail live events for all registered resource kinds."""

    async def authenticate(
        self, payload: EventPayload, headers: dict[str, Any]
    ) -> bool:
        if not await is_aws_v3_live_events_enabled():
            logger.warning("AWS-v3 live events are disabled by organization feature flag")
            return False

        expected_api_key = ocean.integration_config.get("live_events_api_key")
        if not expected_api_key:
            logger.warning(
                "liveEventsApiKey is not configured; rejecting all live events"
            )
            return False

        provided_api_key = self._get_auth_header_value(headers)
        return provided_api_key == expected_api_key

    @staticmethod
    def _get_auth_header_value(headers: dict[str, Any]) -> str | None:
        expected_header_name = LIVE_EVENTS_API_KEY_HEADER.lower()
        for header_name, value in headers.items():
            if header_name.lower() == expected_header_name:
                return str(value)
        return None

    async def should_process_event(self, event: WebhookEvent) -> bool:
        if not await is_aws_v3_live_events_enabled():
            return False
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

        metadata = kind_to_export_metadata.get(ObjectKind(parsed.kind))
        if metadata is None or not metadata.supports_live_events:
            logger.warning(
                f"No live event metadata for kind {parsed.kind}; skipping live event"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        live_event_context = LiveEventContext(
            identifier=parsed.identifier,
            account_id=parsed.account_id,
            region=parsed.region,
        )
        live_events = metadata.live_events

        if parsed.action == CloudTrailEventAction.DELETE:
            logger.info(
                f"Processing {parsed.kind} delete live event: {parsed.identifier}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[
                    {
                        "Type": parsed.kind,
                        "Properties": live_events.delete_properties_factory(
                            live_event_context
                        ),
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

        exporter = metadata.exporter(session)
        options = live_events.request_factory(live_event_context, include_actions)

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
                            "Properties": live_events.delete_properties_factory(
                                live_event_context
                            ),
                        }
                    ],
                )
            raise

        return WebhookEventRawResults(
            updated_raw_results=[resource], deleted_raw_results=[]
        )
