from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortAppConfig,
    Selector,
)
import typing
from pydantic import Field


class AWSSpecificKindsResourceConfig(Selector):
    resource_kinds: list[str] = Field(alias="resourceKinds", default=[], min_items=1)


class AWSResourceConfig(ResourceConfig):
    kind: typing.Literal["cloudResource"]
    selector: AWSSpecificKindsResourceConfig


class AWSPortAppConfig(PortAppConfig):
    resources: list[AWSResourceConfig | ResourceConfig] = Field(default_factory=list)
