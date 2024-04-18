import typing

from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from pydantic import Field, validator


class GCPCloudResourceSelector(Selector):
    resource_kinds: list[str] = Field(
        alias="resourceKinds",
    )

    @validator("resource_kinds")
    def validate_resource_kinds_min_size(cls, v: list[str]) -> list[str]:
        if len(v) < 1:
            raise ValueError("resourceKinds must have at least one item")
        return v


class GCPCloudResourceConfig(ResourceConfig):
    kind: typing.Literal["cloudResource"]
    selector: GCPCloudResourceSelector


class GCPPortAppConfig(PortAppConfig):
    resources: list[GCPCloudResourceConfig | ResourceConfig] = Field(
        default_factory=list
    )
