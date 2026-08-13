from aws.core.helpers.metadata.types import (
    CloudTrailDetail,
    CloudTrailEventAction,
    CloudTrailEventMapping,
    LiveEventContext,
    LiveEventFactories,
)
from aws.core.exporters.s3.bucket.models import SingleBucketRequest
from aws.utils import RegionHelper


def _bucket_arn(bucket_name: str) -> str:
    partition = RegionHelper.get_partition()
    return f"arn:{partition}:s3:::{bucket_name}"


def _extract_s3_bucket_name(detail: CloudTrailDetail) -> str | None:
    bucket_name = detail.get("requestParameters", {}).get("bucketName")
    return bucket_name if isinstance(bucket_name, str) else None


def _request_factory(
    context: LiveEventContext, include_actions: list[str]
) -> SingleBucketRequest:
    return SingleBucketRequest(
        bucket_name=context.identifier,
        region=context.region,
        account_id=context.account_id,
        include=include_actions,
    )


def _deletion_identifier_properties(context: LiveEventContext) -> dict[str, str]:
    return {
        "Arn": _bucket_arn(context.identifier),
        "BucketName": context.identifier,
    }


S3_BUCKET_LIVE_EVENTS = LiveEventFactories(
    request_factory=_request_factory,
    deletion_identifier_properties_factory=_deletion_identifier_properties,
    cloudtrail_mappings={
        "CreateBucket": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT, _extract_s3_bucket_name
        ),
        "DeleteBucket": CloudTrailEventMapping(
            CloudTrailEventAction.DELETE, _extract_s3_bucket_name
        ),
    },
)
