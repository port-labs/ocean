from typing import Literal

from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from pydantic import Field


class JiraIssueSelector(Selector):
    jql: str | None = Field(
        default=None,
        title="JQL",
        description="JQL query to filter issues.",
    )
    fields: str | None = Field(
        title="Fields",
        description="the list of fields to return for each issue. By default, all navigable fields are returned.",
        default="*all",
    )


class JiraIssueConfig(ResourceConfig):
    kind: Literal["issue"] = Field(
        title="Jira Issue",
        description="Jira Server issue resource kind.",
    )
    selector: JiraIssueSelector = Field(
        title="Issue Selector",
        description="Selector for the Jira Server issue resource.",
    )


class JiraProjectSelector(Selector):
    expand: str = Field(
        title="Expand",
        default="",
        description="A comma-separated list of the parameters to expand",
    )


class JiraProjectConfig(ResourceConfig):
    kind: Literal["project"] = Field(
        title="Jira Project",
        description="Jira Server project resource kind.",
    )
    selector: JiraProjectSelector = Field(
        title="Project Selector",
        description="Selector for the Jira Server project resource.",
    )


class JiraUserConfig(ResourceConfig):
    kind: Literal["user"] = Field(
        title="Jira User",
        description="Jira Server user resource kind.",
    )


class JiraServerPortAppConfig(PortAppConfig):
    resources: list[
        JiraIssueConfig | JiraProjectConfig | JiraUserConfig
    ] = Field(
        default_factory=list
    )  # type: ignore[assignment]
