from enum import StrEnum
from typing import List, Literal

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
)
from port_ocean.core.integrations.base import BaseIntegration
from pydantic.v1 import Field


class ObjectKind(StrEnum):
    ENTITY = "scale-quality-entity"


class ScaleQualityEntityResourceConfig(ResourceConfig):
    kind: Literal["scale-quality-entity"] = Field(
        description=(
            "Every ScaleQuality organization, business unit and team, "
            "with its measured quality signals."
        ),
        title="ScaleQuality Entity",
    )


class ScaleQualityPortAppConfig(PortAppConfig):
    resources: List[ScaleQualityEntityResourceConfig] = Field(  # type: ignore[assignment]
        description="Resources for ScaleQuality",
        title="Resources",
        default_factory=list,
    )


class ScaleQualityIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = ScaleQualityPortAppConfig
