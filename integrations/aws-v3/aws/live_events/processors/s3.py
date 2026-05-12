from typing import Any

from aiobotocore.session import AioSession
from loguru import logger
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventRawResults

from aws.core.exporters.s3.bucket.exporter import S3BucketExporter
from aws.core.exporters.s3.bucket.models import SingleBucketRequest
from aws.live_events.processors.base import BaseLiveEventProcessor

_UPSERT_EVENT_NAMES: frozenset[str] = frozenset({"CreateBucket"})
_DELETE_EVENT_NAMES: frozenset[str] = frozenset({"DeleteBucket"})
_ALL_EVENT_NAMES: frozenset[str] = _UPSERT_EVENT_NAMES | _DELETE_EVENT_NAMES


class S3LiveEventProcessor(BaseLiveEventProcessor):
    """Handles S3 bucket lifecycle events delivered via CloudTrail."""

    kinds = ["AWS::S3::Bucket"]
    detail_types = ["AWS API Call via CloudTrail"]

    def can_handle(self, detail_type: str, detail: dict[str, Any]) -> bool:
        if detail_type != "AWS API Call via CloudTrail":
            return False
        event_source: str = detail.get("eventSource", "")
        event_name: str = detail.get("eventName", "")
        return "s3" in event_source and event_name in _ALL_EVENT_NAMES

    async def handle(
        self,
        event: dict[str, Any],
        account_id: str,
        region: str,
        session: AioSession,
    ) -> WebhookEventRawResults:
        detail = event.get("detail", {})
        event_name: str = detail.get("eventName", "")
        request_params: dict[str, Any] = detail.get("requestParameters") or {}
        bucket_name: str = request_params.get("bucketName", "")

        logger.info(
            "Handling S3 CloudTrail event",
            extra={
                "id": bucket_name,
                "event_name": event_name,
                "region": region,
                "account": account_id,
                "detail_type": "AWS API Call via CloudTrail",
            },
        )

        if not bucket_name:
            logger.warning(
                "S3 CloudTrail event missing bucketName in requestParameters — skipping",
                extra={"event_name": event_name, "reason": "missing_id"},
            )
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        if event_name in _DELETE_EVENT_NAMES:
            logger.info(
                f"S3 bucket '{bucket_name}' deleted — marking for deletion",
                extra={"id": bucket_name, "outcome": "delete"},
            )
            stub = {
                "Type": "AWS::S3::Bucket",
                "Properties": {"BucketName": bucket_name},
            }
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[stub])

        # since S3 is a global service, we pass the event region as the request region so the
        # bucket can be described from the same endpoint that served the CloudTrail event.
        exporter = S3BucketExporter(session)
        options = SingleBucketRequest(
            bucket_name=bucket_name,
            region=region,
            include=[],
            account_id=account_id,
        )
        try:
            resource = await exporter.get_resource(options)
        except Exception as exc:
            logger.error(
                f"Failed to fetch S3 bucket '{bucket_name}': {exc}",
                extra={"id": bucket_name, "outcome": "error"},
            )
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        if not resource:
            logger.warning(
                f"S3 bucket '{bucket_name}' not found — skipping",
                extra={"id": bucket_name, "reason": "not_found"},
            )
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        logger.info(
            f"S3 bucket '{bucket_name}' fetched — upserting",
            extra={"id": bucket_name, "outcome": "upsert"},
        )
        return WebhookEventRawResults(updated_raw_results=[resource], deleted_raw_results=[])
