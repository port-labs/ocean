from typing import Literal

from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from pydantic import Field


class TeamSelector(Selector):
    include_members: bool = Field(
        alias="includeMembers",
        default=False,
        description="Whether to include the members of the team, defaults to false",
    )


class TeamResourceConfig(ResourceConfig):
    kind: Literal["team"]
    selector: TeamSelector


class JiraIssueSelector(Selector):
    jql: str | None = None
    fields: str | None = Field(
        description="Additional fields to be included in the API response",
        default="*all",
    )
    expand: str | None = None


class JiraIssueConfig(ResourceConfig):
    selector: JiraIssueSelector
    kind: Literal["issue"]


class JiraProjectSelector(Selector):
    expand: str = Field(
        description="A comma-separated list of the parameters to expand.",
        default="insight",
    )


class JiraProjectResourceConfig(ResourceConfig):
    selector: JiraProjectSelector
    kind: Literal["project"]


class JiraPortAppConfig(PortAppConfig):
    resources: list[
        TeamResourceConfig
        | JiraIssueConfig
        | JiraProjectResourceConfig
        | ResourceConfig
    ]
