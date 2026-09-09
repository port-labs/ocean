from typing import TYPE_CHECKING

from linear.client.constants import LinearObject
from linear.core.exporters.base_exporter import (
    GetOptions,
    PaginatedExporter,
    SingleResourceExporter,
)

if TYPE_CHECKING:
    from integration import LabelResourceConfig


class GetLabelOptions(GetOptions["LabelResourceConfig"]):
    @classmethod
    def from_resource_config(
        cls, resource_config: "LabelResourceConfig", *, resource_id: str
    ) -> "GetLabelOptions":
        return cls(resource_id=resource_id)


class LabelExporter(PaginatedExporter, SingleResourceExporter[GetLabelOptions]):
    object_type = LinearObject.LABELS
