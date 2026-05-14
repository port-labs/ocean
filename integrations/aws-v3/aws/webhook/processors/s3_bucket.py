from __future__ import annotations

from typing import Any, ClassVar

from aws.core.exporters.s3.bucket.exporter import S3BucketExporter
from aws.core.exporters.s3.bucket.models import SingleBucketRequest
from aws.core.helpers.types import ObjectKind
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_models import ResourceRequestModel
from aws.webhook.events import (
    S3_DELETE_EVENT_NAMES,
    S3_EVENT_SOURCE,
    S3_UPSERT_EVENT_NAMES,
    EventBridgeDetailType,
)
from aws.webhook.processors.base import AWSLiveEventProcessor


class S3BucketWebhookProcessor(AWSLiveEventProcessor):
    kind: ClassVar[str] = ObjectKind.S3_BUCKET
    detail_types: ClassVar[frozenset[str]] = frozenset(
        {EventBridgeDetailType.CLOUDTRAIL_API_CALL.value}
    )
    event_sources: ClassVar[frozenset[str]] = frozenset({S3_EVENT_SOURCE})
    exporter_cls: ClassVar[type[IResourceExporter] | None] = S3BucketExporter

    def extract_identifier(self, envelope: dict[str, Any]) -> dict[str, Any] | None:
        detail = envelope.get("detail") or {}
        event_name = detail.get("eventName", "")
        if (
            event_name not in S3_UPSERT_EVENT_NAMES
            and event_name not in S3_DELETE_EVENT_NAMES
        ):
            return None
        bucket_name = (detail.get("requestParameters") or {}).get("bucketName")
        if not isinstance(bucket_name, str) or not bucket_name:
            return None
        return {"BucketName": bucket_name}

    def is_delete(self, envelope: dict[str, Any]) -> bool:
        detail = envelope.get("detail") or {}
        return detail.get("eventName") in S3_DELETE_EVENT_NAMES

    def build_request(
        self,
        identifier: dict[str, Any],
        account_id: str,
        region: str,
        include: list[str],
    ) -> ResourceRequestModel:
        return SingleBucketRequest(
            region=region,
            account_id=account_id,
            include=include,
            bucket_name=identifier["BucketName"],
        )
