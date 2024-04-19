import typing

from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from pydantic import Field


class GCPCloudResourceSelector(Selector):
    resource_kinds: list[str] = Field(alias="resourceKinds", min_items=1)


class GCPCloudResourceConfig(ResourceConfig):
    kind: typing.Literal["cloudResource"]
    selector: GCPCloudResourceSelector


class GCPPortAppConfig(PortAppConfig):
    resources: list[GCPCloudResourceConfig | ResourceConfig] = Field(
        default_factory=list
    )
