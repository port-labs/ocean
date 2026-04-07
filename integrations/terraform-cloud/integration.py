from typing import Literal

from pydantic import Field

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration


class StateFileSelector(Selector):
    current_only: bool = Field(
        alias="currentOnly",
        default=True,
        description="If true, fetch only the current state file per workspace. If false, fetch all historical state files.",
    )


class StateFileResourceConfig(ResourceConfig):
    kind: Literal["state-file"]
    selector: StateFileSelector


class TerraformCloudPortAppConfig(PortAppConfig):
    resources: list[StateFileResourceConfig | ResourceConfig] = Field(
        default_factory=list
    )


class TerraformCloudIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = TerraformCloudPortAppConfig
