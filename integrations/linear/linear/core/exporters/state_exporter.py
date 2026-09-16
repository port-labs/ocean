from typing import TYPE_CHECKING

from linear.client.constants import LinearObject
from linear.core.exporters.base_exporter import (
    GetOptions,
    PaginatedExporter,
    SingleResourceExporter,
)

if TYPE_CHECKING:
    from integration import StateResourceConfig


class GetStateOptions(GetOptions["StateResourceConfig"]):
    @classmethod
    def from_resource_config(
        cls, resource_config: "StateResourceConfig", *, resource_id: str
    ) -> "GetStateOptions":
        return cls(resource_id=resource_id)


class StateExporter(PaginatedExporter, SingleResourceExporter[GetStateOptions]):
    object_type = LinearObject.WORKFLOW_STATES
