from typing import Any
from loguru import logger

from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEventRawResults,
    WebhookEvent,
)

from aws.core.exporters.s3.bucket.exporter import S3BucketExporter
from aws.core.exporters.s3.bucket.models import SingleBucketRequest
from aws.auth import session_factory


class S3EventHandler:
    def __init__(self, event: WebhookEvent) -> None:
        self.event = event

    async def handle(self, payload: EventPayload, resource_config) -> WebhookEventRawResults:
        detail = payload.get("detail", {})
        bucket = detail.get("bucket") or detail.get("requestParameters", {}).get("bucketName")
        region = payload.get("region") or detail.get("awsRegion")
        account = payload.get("account") or detail.get("accountId")

        if not bucket:
            logger.warning("S3 event missing bucket; skipping")
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        session = await session_factory.get_session_for_account(account)
        exporter = S3BucketExporter(session)
        options = SingleBucketRequest(bucket_name=bucket, region=region, account_id=account)

        try:
            resource = await exporter.get_resource(options)
            if not resource:
                return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[{"BucketName": bucket, "AccountId": account, "Region": region}])
            return WebhookEventRawResults(updated_raw_results=[resource], deleted_raw_results=[])
        except Exception as e:
            logger.error(f"Failed to fetch S3 bucket {bucket}: {e}")
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])
