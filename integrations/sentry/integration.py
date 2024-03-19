from pydantic.fields import Field

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration


class SentrySelector(Selector):
    tag: str | None = Field(
        default="environment",
        alias="tag",
        description="The name of the tag used to filter the resources. The default value is environment",
    )


class SentryResourceConfig(ResourceConfig):
    selector: SentrySelector


class SentryPortAppConfig(PortAppConfig):
    resources: list[SentryResourceConfig] = Field(default_factory=list)  # type: ignore


class SentryIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = SentryPortAppConfig
