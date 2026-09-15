from typing import TYPE_CHECKING

from linear.client.constants import LinearObject
from linear.core.exporters.base_exporter import (
    GetOptions,
    PaginatedExporter,
    SingleResourceExporter,
)

if TYPE_CHECKING:
    from integration import ProjectResourceConfig


class GetProjectOptions(GetOptions["ProjectResourceConfig"]):
    @classmethod
    def from_resource_config(
        cls, resource_config: "ProjectResourceConfig", *, resource_id: str
    ) -> "GetProjectOptions":
        return cls(resource_id=resource_id)


class ProjectExporter(PaginatedExporter, SingleResourceExporter[GetProjectOptions]):
    object_type = LinearObject.PROJECTS
