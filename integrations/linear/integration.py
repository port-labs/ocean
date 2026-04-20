from typing import Literal

from pydantic import Field

from linear.utils import ObjectKind
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
)
from port_ocean.core.integrations.base import BaseIntegration


class TeamResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.TEAM] = Field(
        title="Linear Team",
        description="Linear team resource kind.",
    )


class LabelResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.LABEL] = Field(
        title="Linear Label",
        description="Linear label resource kind.",
    )


class IssueResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.ISSUE] = Field(
        title="Linear Issue",
        description="Linear issue resource kind.",
    )


class LinearPortAppConfig(PortAppConfig):
    resources: list[
        TeamResourceConfig | LabelResourceConfig | IssueResourceConfig
    ] = Field(
        default_factory=list,
    )  # type: ignore[assignment]


class LinearIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = LinearPortAppConfig
