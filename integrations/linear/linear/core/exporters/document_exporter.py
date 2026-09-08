from typing import TYPE_CHECKING

from linear.client.constants import LinearObject
from linear.core.exporters.base_exporter import (
    GetOptions,
    PaginatedExporter,
    SingleResourceExporter,
)

if TYPE_CHECKING:
    from integration import DocumentResourceConfig


class GetDocumentOptions(GetOptions["DocumentResourceConfig"]):
    @classmethod
    def from_resource_config(
        cls, resource_config: "DocumentResourceConfig", *, resource_id: str
    ) -> "GetDocumentOptions":
        return cls(resource_id=resource_id)


class DocumentExporter(
    PaginatedExporter,
    SingleResourceExporter[GetDocumentOptions],
):
    object_type = LinearObject.DOCUMENTS
