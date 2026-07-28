from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from aws.core.exporters.s3 import S3BucketExporter
from aws.core.exporters.s3.bucket.models import SingleBucketRequest
from aws.core.helpers.types import ObjectKind
from aws.core.modeling.resource_models import ResourceRequestModel
from aws.utils import RegionHelper
from aws.webhook.cloudtrail_parser import NormalizedEvent


@dataclass(frozen=True)
class ExporterBinding:
    exporter_cls: type[Any]
    request_factory: Callable[[NormalizedEvent, list[str]], ResourceRequestModel]
    delete_properties_factory: Callable[[NormalizedEvent], dict[str, str]]


def _s3_bucket_arn(bucket_name: str) -> str:
    partition = RegionHelper.get_partition()
    return f"arn:{partition}:s3:::{bucket_name}"


def _s3_bucket_delete_properties(event: NormalizedEvent) -> dict[str, str]:
    return {"Arn": _s3_bucket_arn(event.identifier), "BucketName": event.identifier}


def _s3_bucket_request_factory(
    event: NormalizedEvent, include_actions: list[str]
) -> SingleBucketRequest:
    return SingleBucketRequest(
        bucket_name=event.identifier,
        region=event.region,
        account_id=event.account_id,
        include=include_actions,
    )


EXPORTER_REGISTRY: dict[str, ExporterBinding] = {
    ObjectKind.S3_BUCKET: ExporterBinding(
        exporter_cls=S3BucketExporter,
        request_factory=_s3_bucket_request_factory,
        delete_properties_factory=_s3_bucket_delete_properties,
    ),
}
