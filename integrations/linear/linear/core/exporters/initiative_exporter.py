from typing import TYPE_CHECKING

from linear.client.constants import LinearObject
from linear.core.exporters.base_exporter import (
    GetOptions,
    PaginatedExporter,
    SingleResourceExporter,
)

if TYPE_CHECKING:
    from integration import InitiativeResourceConfig


class GetInitiativeOptions(GetOptions["InitiativeResourceConfig"]):
    @classmethod
    def from_resource_config(
        cls, resource_config: "InitiativeResourceConfig", *, resource_id: str
    ) -> "GetInitiativeOptions":
        return cls(resource_id=resource_id)


class InitiativeExporter(PaginatedExporter, SingleResourceExporter[GetInitiativeOptions]):
    object_type = LinearObject.INITIATIVES
