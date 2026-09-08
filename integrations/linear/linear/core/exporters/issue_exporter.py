from typing import TYPE_CHECKING

from linear.client.constants import LinearObject
from linear.core.exporters.base_exporter import (
    GetOptions,
    PaginatedExporter,
    SingleResourceExporter,
)

if TYPE_CHECKING:
    from integration import IssueResourceConfig


class GetIssueOptions(GetOptions["IssueResourceConfig"]):
    @classmethod
    def from_resource_config(
        cls, resource_config: "IssueResourceConfig", *, resource_id: str
    ) -> "GetIssueOptions":
        return cls(resource_id=resource_id)


class IssueExporter(PaginatedExporter, SingleResourceExporter[GetIssueOptions]):
    object_type = LinearObject.ISSUES
