from typing import Any

from aws.core.helpers.types import ObjectKind
from aws.webhook.event_name_mappings.mapping import CloudTrailEventAction, EventNameMapping


def _extract_s3_bucket_name(detail: dict[str, Any]) -> str | None:
    bucket_name = detail.get("requestParameters", {}).get("bucketName")
    return bucket_name if isinstance(bucket_name, str) and bucket_name else None


S3_MAPPINGS: dict[str, EventNameMapping] = {
    "CreateBucket": EventNameMapping(
        ObjectKind.S3_BUCKET, CloudTrailEventAction.UPSERT, _extract_s3_bucket_name
    ),
    "DeleteBucket": EventNameMapping(
        ObjectKind.S3_BUCKET, CloudTrailEventAction.DELETE, _extract_s3_bucket_name
    ),
}
