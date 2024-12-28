from typing import Annotated, Literal, Union

from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from pydantic import BaseModel, Field


class TeamSelector(Selector):
    include_members: bool = Field(
        alias="includeMembers",
        default=False,
        description="Whether to include the members of the team, defaults to false",
    )


class TeamResourceConfig(ResourceConfig):
    kind: Literal["team"]
    selector: TeamSelector


class JiraResourceConfig(ResourceConfig):
    class Selector(BaseModel):
        query: str
        jql: str | None = None

    selector: Selector  # type: ignore
    kind: Literal["issue", "user"]


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
        TeamResourceConfig | JiraResourceConfig | JiraProjectResourceConfig
    ] = Field(
        default_factory=list
    )  # type: ignore
