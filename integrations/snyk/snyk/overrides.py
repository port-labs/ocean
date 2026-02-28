import typing

from port_ocean.core.handlers import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortAppConfig,
    Selector,
)
from pydantic import Field
from typing import Literal
from port_ocean.core.integrations.base import BaseIntegration


class ProjectSelector(Selector):
    attach_issues_to_project: bool = Field(alias="attachIssuesToProject", default=True)


class ProjectResourceConfig(ResourceConfig):
    kind: typing.Literal["project"]
    selector: ProjectSelector


class TargetSelector(Selector):
    attach_project_data: bool = Field(default=True, alias="attachProjectData")


class TargetResourceConfig(ResourceConfig):
    kind: Literal["target"]
    selector: TargetSelector


class SnykPortAppConfig(PortAppConfig):
    resources: list[ProjectResourceConfig | TargetResourceConfig | ResourceConfig] = (
        Field(default_factory=list)
    )


class SnykIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = SnykPortAppConfig
