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


class FactoryAIPortAppConfig(PortAppConfig):
    resources: list[EnvironmentResourceConfig] = Field(
        description="Resources for factory-ai",
        title="Resources",
        default_factory=list,
    )  # type: ignore[assignment]
