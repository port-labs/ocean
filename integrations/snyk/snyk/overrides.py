import typing

from port_ocean.core.handlers import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortAppConfig,
    Selector,
)
from pydantic import Field

from port_ocean.core.integrations.base import BaseIntegration


class ProjectSelector(Selector):
    attach_issues_to_project: bool = Field(alias="attachIssuesToProject", default=True)


class ProjectResourceConfig(ResourceConfig):
    kind: typing.Literal["project"]
    selector: ProjectSelector


class SnykPortAppConfig(PortAppConfig):
    resources: list[ProjectResourceConfig | ResourceConfig] = Field(
        default_factory=list
    )


class SnykIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = SnykPortAppConfig
