import typing

from port_ocean.core.handlers import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortAppConfig,
)
from pydantic import Field

from port_ocean.core.integrations.base import BaseIntegration


class FindingResourceConfig(ResourceConfig):
    kind: typing.Literal["finding"]
    selector: True


class JitPortAppConfig(PortAppConfig):
    resources: list[FindingResourceConfig | ResourceConfig] = Field(
        default_factory=list
    )


class JitIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = JitPortAppConfig
