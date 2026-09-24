from enum import StrEnum
from typing import Literal

from pydantic.v1 import Field

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
)
from port_ocean.core.integrations.base import BaseIntegration


class ObjectKind(StrEnum):
    EXAMPLE_KIND = "example-kind"


class ExampleKindResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.EXAMPLE_KIND] = Field(
        description="Example kind for plain",
        title="Example Kind",
    )


class PlainPortAppConfig(PortAppConfig):
    resources: list[ExampleKindResourceConfig] = Field(
        description="Resources for plain",
        title="Resources",
        default_factory=list,
    )  # type: ignore[assignment]


class PlainIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = PlainPortAppConfig
