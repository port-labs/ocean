from pydantic.fields import Field
from typing import Literal


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


class TeamSelector(Selector):
    include_members: bool = Field(
        alias="includeMembers",
        default=False,
        description="Whether to include the members of the team, defaults to false",
    )


class SentryResourceConfig(ResourceConfig):
    selector: SentrySelector
    kind: Literal["project", "issue", "project-tag", "issue-tag"]


class TeamResourceConfig(ResourceConfig):
    kind: Literal["team"]
    selector: TeamSelector


class SentryPortAppConfig(PortAppConfig):
    resources: list[SentryResourceConfig | TeamResourceConfig | ResourceConfig] = Field(
        default_factory=list
    )


class SentryIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = SentryPortAppConfig
