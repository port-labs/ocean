import typing

from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortAppConfig,
    Selector,
)
from pydantic import Field


class IssueSelector(Selector):
    status_list: list[str] = Field(
        alias="statusList",
        description="List of statuses to filter issues by",
        default=["OPEN", "IN_PROGRESS"],
    )


class IssueResourceConfig(ResourceConfig):
    kind: typing.Literal["issue"]
    selector: IssueSelector


class WizPortAppConfig(PortAppConfig):
    resources: list[IssueResourceConfig | ResourceConfig] = Field(default_factory=list)
