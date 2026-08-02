from dataclasses import dataclass
from typing import Any

from aws.core.exporters.codepipeline import (
    CodePipelineActionExecutionExporter,
    PaginatedCodePipelineActionExecutionRequest,
)
from aws.core.exporters.s3.bucket.exporter import S3BucketExporter
from aws.core.exporters.s3.bucket.models import PaginatedBucketRequest
from aws.core.helpers.types import ObjectKind
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_models import ResourceRequestModel


@dataclass
class ExporterMetadata:
    exporter: type[IResourceExporter[Any]]
    paginated_request_model: type[ResourceRequestModel]
    regional: bool = True


kind_to_export_metadata: dict[ObjectKind, ExporterMetadata] = {
    ObjectKind.S3_BUCKET: ExporterMetadata(
        S3BucketExporter, PaginatedBucketRequest, regional=False
    ),
    ObjectKind.CODEPIPELINE_ACTION_EXECUTION: ExporterMetadata(
        CodePipelineActionExecutionExporter, PaginatedCodePipelineActionExecutionRequest
    ),
}
