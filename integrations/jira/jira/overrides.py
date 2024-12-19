from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from pydantic import BaseModel, Field
from typing import Literal


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


class JiraPortAppConfig(PortAppConfig):
    resources: list[TeamResourceConfig | JiraResourceConfig] = Field(
        default_factory=list
    )  # type: ignore
