"""Thin POC webhook processor for AWS::S3::Bucket live events.

Scope of this POC (intentionally minimal):
- Only S3 bucket create/delete CloudTrail events are handled.
- Delivery is assumed to be an EventBridge API Destination POST'ing the
  EventBridge envelope (with the CloudTrail event under ``detail``) directly
  to this integration's webhook endpoint.
- Authentication is a simple shared-secret header comparison
  (``x-port-aws-ocean-api-key``), matching the ``liveEventsApiKey`` the
  customer configures on the EventBridge Connection.
- No queuing/dedupe beyond what Ocean's webhook framework already provides.

This is NOT meant to be production-ready. See
``integrations/aws-v3/docs/live-events-project.md`` for the full project plan
(multi-kind support, dedupe, CloudTrail parser coverage, IaC, etc).
"""

from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from aws.auth.session_factory import get_session_for_account
from aws.core.exporters.s3 import S3BucketExporter
from aws.core.exporters.s3.bucket.models import SingleBucketRequest
from aws.core.helpers.types import ObjectKind
from aws.core.helpers.utils import (
    is_access_denied_exception,
    is_resource_not_found_exception,
)
from aws.events.cloudtrail_parser import (
    S3BucketLiveEventAction,
    is_supported_s3_bucket_event,
    parse_s3_bucket_event,
)

LIVE_EVENTS_API_KEY_HEADER = "x-port-aws-ocean-api-key"


class S3BucketWebhookProcessor(AbstractWebhookProcessor):
    """Handles S3 bucket create/delete live events (POC)."""

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return is_supported_s3_bucket_event(event.payload)

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.S3_BUCKET]

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        expected_api_key = ocean.integration_config.get("live_events_api_key")
        if not expected_api_key:
            logger.warning(
                "liveEventsApiKey is not configured; rejecting all live events"
            )
            return False

        provided_api_key = headers.get(LIVE_EVENTS_API_KEY_HEADER)
        return provided_api_key == expected_api_key

    async def validate_payload(self, payload: EventPayload) -> bool:
        return parse_s3_bucket_event(payload) is not None

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        parsed = parse_s3_bucket_event(payload)
        if parsed is None:
            logger.warning("Received an unparsable S3 bucket live event, skipping")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        if parsed.action == S3BucketLiveEventAction.DELETE:
            logger.info(f"Processing S3 bucket delete live event: {parsed.bucket_name}")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[
                    {
                        "Type": ObjectKind.S3_BUCKET,
                        "Properties": {"BucketName": parsed.bucket_name},
                    }
                ],
            )

        logger.info(
            f"Processing S3 bucket {parsed.event_name} live event: {parsed.bucket_name} "
            f"(account={parsed.account_id}, region={parsed.region})"
        )

        session = await get_session_for_account(parsed.account_id)
        if session is None:
            logger.warning(
                f"No session available for account {parsed.account_id}; "
                f"skipping live event for bucket {parsed.bucket_name}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        exporter = S3BucketExporter(session)
        options = SingleBucketRequest(
            bucket_name=parsed.bucket_name,
            region=parsed.region,
            account_id=parsed.account_id,
        )

        try:
            resource = await exporter.get_resource(options)
        except Exception as error:
            if is_access_denied_exception(error) or is_resource_not_found_exception(
                error
            ):
                logger.warning(
                    f"Could not fetch bucket {parsed.bucket_name} after live event "
                    f"({error}); treating as deleted"
                )
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[
                        {
                            "Type": ObjectKind.S3_BUCKET,
                            "Properties": {"BucketName": parsed.bucket_name},
                        }
                    ],
                )
            raise

        return WebhookEventRawResults(
            updated_raw_results=[resource], deleted_raw_results=[]
        )
