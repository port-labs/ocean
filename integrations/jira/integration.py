from typing import Literal

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from pydantic.fields import Field

SprintState = Literal["active", "closed", "future"]


class JiraIssueSelector(Selector):
    jql: str | None = Field(
        description="Jira Query Language (JQL) query to filter issues",
    )
    source: Literal["sprint", "all"] = Field(
        default="all",
        description="Where issues are sourced from",
    )
    # when resyncing issues, there is no way to retrieve the config
    # set for the `sprint` kind, so we need to duplicate the state
    # field. This is redundant, but necessary.
    sprintState: SprintState | None = Field(
        default="active",
        description="State of the sprint",
    )


class JiraSprintSelector(Selector):
    state: SprintState | None = Field(
        default="active",
        description="State of the sprint",
    )


class JiraIssueResourceConfig(ResourceConfig):
    kind: Literal["issue"]
    selector: JiraIssueSelector


class JiraSprintResourceConfig(ResourceConfig):
    kind: Literal["sprint"]
    selector: JiraSprintSelector


class JiraPortAppConfig(PortAppConfig):
    resources: list[
        JiraIssueResourceConfig | JiraSprintResourceConfig | ResourceConfig
    ] = Field(default_factory=list)


class JiraIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = JiraPortAppConfig
