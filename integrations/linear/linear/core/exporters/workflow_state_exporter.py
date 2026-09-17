from typing import TYPE_CHECKING

from linear.client.constants import LinearObject
from linear.core.exporters.base_exporter import (
    GetOptions,
    PaginatedExporter,
    SingleResourceExporter,
)

if TYPE_CHECKING:
    from integration import WorkflowStateResourceConfig


class GetWorkflowStateOptions(GetOptions["WorkflowStateResourceConfig"]):
    @classmethod
    def from_resource_config(
        cls, resource_config: "WorkflowStateResourceConfig", *, resource_id: str
    ) -> "GetWorkflowStateOptions":
        return cls(resource_id=resource_id)


class WorkflowStateExporter(
    PaginatedExporter, SingleResourceExporter[GetWorkflowStateOptions]
):
    object_type = LinearObject.WORKFLOW_STATES
