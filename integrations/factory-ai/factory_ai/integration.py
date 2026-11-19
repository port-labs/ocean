from typing import Literal

from pydantic.v1 import Field
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
)


class EnvironmentResourceConfig(ResourceConfig):
    kind: Literal["environment"] = Field(
        description="Factory environment resource kind",
        title="Environment",
    )


class ComputerResourceConfig(ResourceConfig):
    kind: Literal["computer"] = Field(
        description="Factory computer resource kind",
        title="Computer",
    )


class UserResourceConfig(ResourceConfig):
    kind: Literal["user"] = Field(
        description="Factory organization user resource kind",
        title="User",
    )


class FactoryAIPortAppConfig(PortAppConfig):
    resources: list[
        EnvironmentResourceConfig | ComputerResourceConfig | UserResourceConfig
    ] = Field(
        description="Resources for factory-ai",
        title="Resources",
        default_factory=list,
    )  # type: ignore[assignment]
