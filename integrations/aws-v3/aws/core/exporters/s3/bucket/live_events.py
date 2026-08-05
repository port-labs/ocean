from aws.core.exporters.metadata.types import LiveEventContext, LiveEventFactories
from aws.core.exporters.s3.bucket.models import SingleBucketRequest
from aws.utils import RegionHelper


def _bucket_arn(bucket_name: str) -> str:
    partition = RegionHelper.get_partition()
    return f"arn:{partition}:s3:::{bucket_name}"


def _request_factory(
    context: LiveEventContext, include_actions: list[str]
) -> SingleBucketRequest:
    return SingleBucketRequest(
        bucket_name=context.identifier,
        region=context.region,
        account_id=context.account_id,
        include=include_actions,
    )


def _delete_properties(context: LiveEventContext) -> dict[str, str]:
    return {
        "Arn": _bucket_arn(context.identifier),
        "BucketName": context.identifier,
    }


LIVE_EVENTS = LiveEventFactories(
    request_factory=_request_factory,
    delete_properties_factory=_delete_properties,
)
