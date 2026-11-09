from dataclasses import dataclass
from typing import Any

from aws_integration.overrides import AWSCustomKindSelector, AWSResourceSelector
from aws.core.exporters.cloudcontrol.resource.exporter import CloudControlExporter
from aws.core.exporters.cloudcontrol.resource.live_events import (
    build_cloud_control_live_events,
)
from aws.core.exporters.cloudcontrol.resource.models import (
    PaginatedCloudControlResourceRequest,
)
from aws.core.exporters.cloudcontrol.resource.scope import (
    resolve_cloud_control_is_regional,
)
from aws.core.helpers.metadata.types import ExporterMetadata


@dataclass
class CloudControlExporterMetadata(ExporterMetadata):
    """Metadata for arbitrary AWS Cloud Control API resource types."""

    type_name: str = ""

    @classmethod
    def for_type(cls, type_name: str) -> "CloudControlExporterMetadata":
        return cls(
            exporter=CloudControlExporter,
            paginated_request_model=PaginatedCloudControlResourceRequest,
            live_events=build_cloud_control_live_events(type_name),
            type_name=type_name,
        )

    def resolve_regional(self, selector: AWSResourceSelector) -> bool:
        if isinstance(selector, AWSCustomKindSelector):
            return resolve_cloud_control_is_regional(
                self.type_name, selector.resource_scope
            )
        return self.regional

    def build_request_extras(
        self, selector: AWSResourceSelector
    ) -> dict[str, Any] | None:
        if not isinstance(selector, AWSCustomKindSelector):
            return None
        return {
            "type_name": self.type_name,
            "use_get_resource_api": selector.use_get_resource_api,
            "resource_scope": selector.resource_scope,
        }
