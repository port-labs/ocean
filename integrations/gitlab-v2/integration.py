from typing import Literal

from port_ocean.core.handlers import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from pydantic import Field


class ProjectSelector(Selector):
    include_languages: bool = Field(
        alias="includeLanguages",
        default=False,
        description="Whether to include the languages of the project, defaults to false",
    )


class ProjectResourceConfig(ResourceConfig):
    kind: Literal["project"]
    selector: ProjectSelector


class GitlabMemberSelector(Selector):
    include_bot_members: bool = Field(
        alias="includeBotMembers",
        default=False,
        description="If set to false, bots will be filtered out from the members list. Default value is true",
    )


class GitlabObjectWithMembersResourceConfig(ResourceConfig):
    kind: Literal["group-with-members"]
    selector: GitlabMemberSelector


class GitlabMemberResourceConfig(ResourceConfig):
    kind: Literal["member"]
    selector: GitlabMemberSelector


class GitlabPortAppConfig(PortAppConfig):
    resources: list[
        ProjectResourceConfig
        | GitlabObjectWithMembersResourceConfig
        | GitlabMemberResourceConfig
        | ResourceConfig
    ] = Field(default_factory=list)


class GitlabIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = GitlabPortAppConfig
