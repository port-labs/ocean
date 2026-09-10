from typing import TYPE_CHECKING

from linear.client.constants import LinearObject
from linear.core.exporters.base_exporter import (
    GetOptions,
    PaginatedExporter,
    SingleResourceExporter,
)

if TYPE_CHECKING:
    from integration import CycleResourceConfig


class GetCycleOptions(GetOptions["CycleResourceConfig"]):
    @classmethod
    def from_resource_config(
        cls, resource_config: "CycleResourceConfig", *, resource_id: str
    ) -> "GetCycleOptions":
        return cls(resource_id=resource_id)


class CycleExporter(PaginatedExporter, SingleResourceExporter[GetCycleOptions]):
    object_type = LinearObject.CYCLES
