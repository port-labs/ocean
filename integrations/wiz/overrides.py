import typing

from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortAppConfig,
    Selector,
)
from pydantic import Field


class IssueSelector(Selector):
    max_pages: int = Field(alias="maxPages", default=20)
    status_list: list[str] = Field(alias="statusList", default_factory=list)


class IssueResourceConfig(ResourceConfig):
    kind: typing.Literal["issue"]
    selector: IssueSelector


class WizPortAppConfig(PortAppConfig):
    resources: list[IssueResourceConfig | ResourceConfig] = Field(default_factory=list)
