from typing import TYPE_CHECKING

from linear.client.constants import LinearObject
from linear.core.exporters.base_exporter import (
    GetOptions,
    PaginatedExporter,
    SingleResourceExporter,
)

if TYPE_CHECKING:
    from integration import UserResourceConfig


class GetUserOptions(GetOptions["UserResourceConfig"]):
    @classmethod
    def from_resource_config(
        cls, resource_config: "UserResourceConfig", *, resource_id: str
    ) -> "GetUserOptions":
        return cls(resource_id=resource_id)


class UserExporter(PaginatedExporter, SingleResourceExporter[GetUserOptions]):
    object_type = LinearObject.USERS
