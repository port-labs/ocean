from aws.core.exporters.s3 import S3BucketExporter
from aws.core.exporters.s3.bucket.models import SingleBucketRequest
from aws.core.helpers.types import ObjectKind
from aws.utils import RegionHelper
from aws.webhook.cloudtrail_parser import NormalizedEvent
from aws.webhook.exporter_bindings.binding import ExporterBinding


def _bucket_arn(bucket_name: str) -> str:
    partition = RegionHelper.get_partition()
    return f"arn:{partition}:s3:::{bucket_name}"


def _delete_properties(event: NormalizedEvent) -> dict[str, str]:
    return {"Arn": _bucket_arn(event.identifier), "BucketName": event.identifier}


def _request_factory(
    event: NormalizedEvent, include_actions: list[str]
) -> SingleBucketRequest:
    return SingleBucketRequest(
        bucket_name=event.identifier,
        region=event.region,
        account_id=event.account_id,
        include=include_actions,
    )


BINDING = ExporterBinding(
    kind=ObjectKind.S3_BUCKET,
    exporter_cls=S3BucketExporter,
    request_factory=_request_factory,
    delete_properties_factory=_delete_properties,
)
