from typing import Any

from aiobotocore.session import AioSession
from loguru import logger

from aws.core.exporters.s3.bucket.exporter import S3BucketExporter
from aws.core.exporters.s3.bucket.models import SingleBucketRequest
from aws.live_events.handlers.base import BaseLiveEventHandler

_DELETE_EVENT_NAMES = {"DeleteBucket"}
_UPSERT_EVENT_NAMES = {"CreateBucket"}


class S3BucketLiveEventHandler(BaseLiveEventHandler):
    kind = "AWS::S3::Bucket"

    def __init__(self, session: AioSession) -> None:
        self._session = session

    async def handle(self, event: dict[str, Any], account_id: str, region: str) -> None:
        detail = event.get("detail", {})
        detail_type: str = event.get("detail-type", "")
        event_name: str = detail.get("eventName", "")

        # S3 CloudTrail events store the bucket name in requestParameters.bucketName.
        request_params: dict[str, Any] = detail.get("requestParameters", {}) or {}
        bucket_name: str = request_params.get("bucketName", "")

        if not bucket_name:
            logger.warning(
                f"[S3] event missing requestParameters.bucketName, skipping",
                extra={"account_id": account_id, "region": region, "detail_type": detail_type, "event_name": event_name},
            )
            return

        logger.info(
            f"[S3] received bucket event",
            extra={
                "kind": self.kind,
                "account_id": account_id,
                "region": region,
                "detail_type": detail_type,
                "event_name": event_name,
                "bucket": bucket_name,
            },
        )

        if event_name in _DELETE_EVENT_NAMES:
            logger.info(f"[S3] bucket {bucket_name} deleted, removing from Port")
            await self._delete(self._build_delete_raw(bucket_name))
            return

        if event_name not in _UPSERT_EVENT_NAMES:
            logger.info(f"[S3] unhandled eventName {event_name!r}, skipping")
            return

        exporter = S3BucketExporter(self._session)
        # S3 is a global service — use us-east-1 as the control-plane region.
        options = SingleBucketRequest(
            region="us-east-1",
            account_id=account_id,
            bucket_name=bucket_name,
            include=[],
        )

        try:
            resource = await exporter.get_resource(options)
        except Exception as exc:
            logger.error(f"[S3] failed to fetch bucket {bucket_name}: {exc}")
            return

        logger.info(
            f"[S3] upserting bucket",
            extra={"kind": self.kind, "account_id": account_id, "region": region, "outcome": "upsert"},
        )
        await self._upsert(resource)
