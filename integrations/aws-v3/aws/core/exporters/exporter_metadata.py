from dataclasses import dataclass

from aws.core.exporters.codepipeline import CodePipelineActionExecutionExporter, \
    PaginatedCodePipelineActionExecutionRequest
from aws.core.helpers.types import ObjectKind
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_models import ResourceRequestModel


@dataclass
class ExporterMetadata:
    exporter: type[IResourceExporter]
    paginated_request_model: type[ResourceRequestModel]
    regional: bool = True


kind_to_export_metadata: dict[ObjectKind, ExporterMetadata] = {
    ObjectKind.CODEPIPELINE_ACTION_EXECUTION: ExporterMetadata(
        CodePipelineActionExecutionExporter, PaginatedCodePipelineActionExecutionRequest
    ),
}
