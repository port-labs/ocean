from typing import Literal
from pydantic import Field, validator

from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)


class TeamSelector(Selector):
    include_members: bool = Field(
        alias="includeMembers",
        title="Include Members",
        default=False,
        description="Whether to fetch and include the list of members for each team. Enabling this will make additional API calls and may increase sync time for large teams.",
    )


class TeamResourceConfig(ResourceConfig):
    kind: Literal["team"] = Field(
        title="Jira Team",
        description="A team in your Jira organization",
    )
    selector: TeamSelector = Field(
        title="Team Selector",
        description="Defines which Jira teams to include and how to query them",
    )


class JiraIssueSelector(Selector):
    jql: str = Field(
        title="JQL Query",
        default="(statusCategory != Done) OR (created >= -1w) OR (updated >= -1w)",
        description="JQL (Jira Query Language) expression used to filter which issues are synced. Defaults to open issues and those created or updated within the last week.",
    )
    fields: str | None = Field(
        title="Included Fields",
        description="Comma-separated list of issue fields to return. Use '*all' to return all fields, or specify individual field names (e.g. 'summary,status,assignee') to reduce payload size.",
        default="*all",
    )
    expand: str | None = Field(
        title="Fields To Expand",
        description="Comma-separated list of additional issue properties to expand. Supported values include 'renderedFields', 'names', 'schema', 'transitions', 'operations', 'editmeta', and 'changelog'.",
        default=None,
    )


class JiraIssueConfig(ResourceConfig):
    selector: JiraIssueSelector = Field(
        title="Issue Selector",
        description="Defines which Jira issues to include and how to query them",
    )
    kind: Literal["issue"] = Field(
        title="Jira Issue",
        description="An issue in your Jira projects, including bugs, tasks, and stories",
    )


class JiraProjectSelector(Selector):
    expand: str = Field(
        title="Expand Properties",
        description="Comma-separated list of additional project properties to expand in the response. Supported values include 'description', 'lead', 'url', 'projectKeys', and 'insight'.",
        default="insight",
    )


class JiraProjectResourceConfig(ResourceConfig):
    selector: JiraProjectSelector = Field(
        title="Project Selector",
        description="Defines which Jira projects to include and how to query them",
    )
    kind: Literal["project"] = Field(
        title="Jira Project",
        description="A project in your Jira account used to organize and track issues",
    )


class JiraUserResourceConfig(ResourceConfig):
    kind: Literal["user"] = Field(
        title="Jira User",
        description="A user account in your Jira organization",
    )


class JiraReleaseResourceConfig(ResourceConfig):
    kind: Literal["release"] = Field(
        title="Jira Release",
        description="A release (version) in a Jira project used to track shipped work",
    )


class JiraBoardSelector(Selector):
    board_type: Literal["scrum", "kanban", "simple"] | None = Field(
        alias="boardType",
        default=None,
        title="Board Type",
        description=("Filter boards by type. Omit to fetch all board types."),
    )
    project_key: str | None = Field(
        alias="projectKey",
        default=None,
        title="Project Key",
        description=(
            "Filter boards scoped to a specific Jira project. "
            "Accepts a project key (e.g. PORT) or project ID."
        ),
    )

    @validator("project_key")
    def project_key_must_not_be_empty(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("projectKey must not be an empty string")
        return v


class JiraBoardResourceConfig(ResourceConfig):
    kind: Literal["board"] = Field(
        title="Jira Board",
        description="Jira board resource kind.",
    )
    selector: JiraBoardSelector = Field(
        title="Board Selector",
        description="Selector for Jira board resources.",
    )


class JiraPortAppConfig(PortAppConfig):
    resources: list[
        TeamResourceConfig
        | JiraIssueConfig
        | JiraProjectResourceConfig
        | JiraUserResourceConfig
        | JiraReleaseResourceConfig
        | JiraBoardResourceConfig
    ] = Field(
        default_factory=list
    )  # type: ignore[assignment]
