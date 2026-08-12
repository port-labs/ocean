"""Unified CloudTrail live-events webhook processor.

All supported kinds share one processor. Per-kind behavior is delegated to
``cloudtrail_parser`` (event normalization) and ``kind_to_export_metadata``
(fetch and delete payloads).
"""

from typing import Any, cast

import hmac

from loguru import logger
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
from aws.core.exporters.exporter_metadata import kind_to_export_metadata
from aws.core.helpers.metadata.types import (
    ExporterMetadata,
    LiveEventContext,
    LiveEventFactories,
)
from aws.core.helpers.types import ObjectKind
from aws.core.helpers.utils import (
    is_access_denied_exception,
    is_resource_not_found_exception,
)
from aws.webhook.cloudtrail_parser import (
    CloudTrailEventAction,
    EventBridgeCloudTrailPayload,
    NormalizedEvent,
    is_supported_cloudtrail_event,
    parse_cloudtrail_event,
)
from aws.config.live_events import get_live_events_api_key
from aws.webhook.consts import LIVE_EVENTS_API_KEY_HEADER
from aws.utils.feature_flags import is_aws_v3_live_events_enabled

_EMPTY_RESULTS = WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])


class CloudTrailWebhookProcessor(AbstractWebhookProcessor):
    """Handles CloudTrail live events for all registered resource kinds."""

    _cached_parsed_event: NormalizedEvent | None = None
    _parsed_event_loaded: bool = False

    def _get_parsed_event(self, payload: EventPayload) -> NormalizedEvent | None:
        if not self._parsed_event_loaded:
            self._cached_parsed_event = parse_cloudtrail_event(
                cast(EventBridgeCloudTrailPayload, payload)
            )
            self._parsed_event_loaded = True
        return self._cached_parsed_event

    async def authenticate(
        self, payload: EventPayload, headers: dict[str, Any]
    ) -> bool:
        if not await is_aws_v3_live_events_enabled():
            logger.debug("AWS-v3 live events are disabled by organization feature flag")
            return False

        expected_api_key = get_live_events_api_key()
        if not expected_api_key:
            logger.warning(
                "live_events_api_key is not configured, rejecting all live events"
            )
            return False

        provided_api_key = self._get_auth_header_value(headers)
        if provided_api_key is None:
            return False
        return hmac.compare_digest(provided_api_key, str(expected_api_key))

    @staticmethod
    def _get_auth_header_value(headers: dict[str, Any]) -> str | None:
        expected_header_name = LIVE_EVENTS_API_KEY_HEADER.lower()
        for header_name, value in headers.items():
            if header_name.lower() == expected_header_name:
                return str(value)
        return None

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return is_supported_cloudtrail_event(
            cast(EventBridgeCloudTrailPayload, event.payload)
        )

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        parsed = self._get_parsed_event(event.payload)
        return [parsed.kind] if parsed is not None else []

    async def validate_payload(self, payload: EventPayload) -> bool:
        return self._get_parsed_event(payload) is not None

    def _resolve_live_event_metadata(
        self, parsed: NormalizedEvent
    ) -> tuple[ExporterMetadata, LiveEventFactories] | None:
        metadata = kind_to_export_metadata.get(ObjectKind(parsed.kind))
        if metadata is None or metadata.live_events is None:
            logger.warning(
                f"No live event metadata for kind {parsed.kind}; skipping live event"
            )
            return None
        return metadata, metadata.live_events

    @staticmethod
    def _build_deletion_result(
        kind: str,
        live_events: LiveEventFactories,
        context: LiveEventContext,
    ) -> WebhookEventRawResults:
        return WebhookEventRawResults(
            updated_raw_results=[],
            deleted_raw_results=[
                {
                    "Type": kind,
                    "Properties": live_events.deletion_identifier_properties_factory(
                        context
                    ),
                }
            ],
        )

    async def _fetch_and_upsert(
        self,
        parsed: NormalizedEvent,
        metadata: ExporterMetadata,
        live_events: LiveEventFactories,
        context: LiveEventContext,
        resource_config: ResourceConfig | None,
    ) -> WebhookEventRawResults:
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
            return _EMPTY_RESULTS

        include_actions: list[str] = []
        if resource_config is not None:
            include_actions = cast(
                AWSResourceConfig, resource_config
            ).selector.include_actions

        exporter = metadata.exporter(session)
        options = live_events.request_factory(context, include_actions)

        try:
            resource = await exporter.get_resource(options)
        except Exception as error:
            if is_resource_not_found_exception(error):
                logger.warning(
                    f"Could not fetch {parsed.kind} {parsed.identifier} after live "
                    f"event ({error}); treating as deleted"
                )
                return self._build_deletion_result(parsed.kind, live_events, context)
            if is_access_denied_exception(error):
                logger.warning(
                    f"Access denied fetching {parsed.kind} {parsed.identifier} after "
                    f"live event ({error}); skipping"
                )
                return _EMPTY_RESULTS
            raise

        return WebhookEventRawResults(
            updated_raw_results=[resource], deleted_raw_results=[]
        )

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig | None
    ) -> WebhookEventRawResults:
        parsed = cast(NormalizedEvent, self._get_parsed_event(payload))
        resolved = self._resolve_live_event_metadata(parsed)
        if resolved is None:
            return _EMPTY_RESULTS

        metadata, live_events = resolved
        context = LiveEventContext(
            identifier=parsed.identifier,
            account_id=parsed.account_id,
            region=parsed.region,
        )

        if parsed.action == CloudTrailEventAction.DELETE:
            logger.info(
                f"Processing {parsed.kind} delete live event: {parsed.identifier}"
            )
            return self._build_deletion_result(parsed.kind, live_events, context)

        return await self._fetch_and_upsert(
            parsed, metadata, live_events, context, resource_config
        )
