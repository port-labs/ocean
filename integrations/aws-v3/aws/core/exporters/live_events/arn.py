from aws.core.exporters.metadata.types import LiveEventContext
from aws.utils import RegionHelper


def s3_bucket_arn(bucket_name: str) -> str:
    partition = RegionHelper.get_partition()
    return f"arn:{partition}:s3:::{bucket_name}"


def regional_service_arn(
    service: str, context: LiveEventContext, resource_path: str
) -> str:
    partition = RegionHelper.get_partition()
    return (
        f"arn:{partition}:{service}:{context.region}:{context.account_id}:"
        f"{resource_path}"
    )
