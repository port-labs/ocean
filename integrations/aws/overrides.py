import typing
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortAppConfig,
    Selector,
)
from pydantic import Field, validator


class AWSSpecificKindsResourceConfig(Selector):
    resource_kinds: list[str] = Field(alias="resourceKinds", default=[])

    @validator("resource_kinds")
    def validate_resource_kinds_min_size(cls, v: dict[str, str]) -> dict[str, str]:
        if len(v) < 1:
            raise ValueError("resourceKinds must have at least one item")
        return v


class AWSResourceConfig(ResourceConfig):
    kind: typing.Literal["cloudResource"]
    selector: AWSSpecificKindsResourceConfig


class AWSPortAppConfig(PortAppConfig):
    resources: list[AWSResourceConfig | ResourceConfig] = Field(default_factory=list)
