from enum import StrEnum
from typing import Literal
from pydantic import Field, validator, BaseModel

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


class JiraSprintSelector(Selector):
    sprint_state: list[Literal["active", "closed", "future"]] | None = Field(
        alias="sprintState",
        default=["active"],
        title="Sprint State",
        min_items=1,
        description=(
            "Filter sprints by state. Accepts a list of states: active, closed, future. "
            "Defaults to ['active'] for performance — closed sprints accumulate over time "
            "and can result in thousands of API calls on large Jira instances. "
            "Set to null to fetch all states. "
            "See: https://developer.atlassian.com/cloud/jira/software/rest/api-group-board/"
            "#api-rest-agile-1-0-board-boardid-sprint-get"
        ),
    )

    @validator("sprint_state", always=True)
    def sprint_state_must_not_contain_duplicates(
        cls, value: list[str] | None
    ) -> list[str] | None:
        if value is None:
            return value
        if len(value) != len(set(value)):
            duplicates = sorted(set(s for s in value if value.count(s) > 1))
            raise ValueError(
                f"sprintState must not contain duplicate values — "
                f"found duplicates: {duplicates}"
            )
        return value


class JiraSprintResourceConfig(ResourceConfig):
    kind: Literal["sprint"] = Field(
        title="Jira Sprint",
        description="Jira sprint resource kind.",
    )
    selector: JiraSprintSelector = Field(
        title="Sprint Selector",
        description="Selector for Jira sprint resources.",
    )


class JiraBacklogSelector(Selector):
    jql: str | None = Field(
        default="updated >= -1w OR statusCategory != Done",
        title="JQL Filter",
        description=(
            "JQL filter applied on top of the board's backlog scope. "
            "Defaults to recently updated or incomplete issues to avoid "
            "re-ingesting the full backlog history on every resync. "
            "Omit entirely to fetch all backlog issues."
        ),
    )
    fields: list[str] | None = Field(
        default=None,
        title="Fields",
        description=(
            "Specific issue fields to return. Omit to return all fields. "
            "Use field projection to reduce payload size on large boards, "
            "e.g. ['id', 'key', 'summary', 'status', 'assignee', 'priority']."
        ),
    )
    use_software_api: bool = Field(
        alias="useSoftwareApi",
        default=True,
        title="Use Software API",
        description=(
            "When true, attempts the newer rest/software/1.0 backlog endpoint first, "
            "falling back to the legacy rest/agile/1.0 endpoint on auth failure. "
            "The agile/1.0 endpoint is deprecated and scheduled for removal on "
            "November 1, 2026. Set to false to force legacy behavior."
        ),
    )


class JiraBacklogResourceConfig(ResourceConfig):
    kind: Literal["backlog"] = Field(
        title="Jira Backlog",
        description="Jira backlog resource kind, representing the set of issues in the backlog of each board.",
    )
    selector: JiraBacklogSelector = Field(
        title="Backlog Selector",
        description="Selector for Jira backlog resources.",
    )


class JiraEpicAPIQueryParams(BaseModel):
    done: Literal["true", "false"] | None = Field(
        default=None,
        title="Done",
        description="Filter epics by completion status. 'true' returns only completed epics, 'false' returns only incomplete epics. Omit to return all epics.",
    )


class JiraEpicSelector(Selector):
    status: list[Literal["incomplete", "complete"]] | None = Field(
        default=["incomplete"],
        title="Epic Status",
        description=(
            "Filter epics by status. Accepts 'complete', 'incomplete', or both. "
            "Omit to fetch all epics regardless of status. "
            "Example: ['incomplete'] fetches only incomplete epics."
        ),
    )

    @property
    def api_query_params(self) -> JiraEpicAPIQueryParams | None:
        if not self.status or len(self.status) != 1:
            return None
        done: Literal["true", "false"] = (
            "true" if self.status[0] == "complete" else "false"
        )
        return JiraEpicAPIQueryParams(done=done)


class JiraEpicResourceConfig(ResourceConfig):
    kind: Literal["epic"] = Field(
        title="Jira Epic",
        description="Jira epic resource kind.",
    )
    selector: JiraEpicSelector = Field(
        title="Epic Selector",
        description="Selector for Jira epic resources.",
    )


class JiraWorklogAPIQueryParams(BaseModel):
    class Config:
        allow_population_by_field_name = True

    started_after: int | None = Field(
        alias="startedAfter",
        default=None,
        title="Started After",
        description="UNIX timestamp in milliseconds. Only return worklogs started after this time.",
    )
    started_before: int | None = Field(
        alias="startedBefore",
        default=None,
        title="Started Before",
        description="UNIX timestamp in milliseconds. Only return worklogs started before this time.",
    )
    expand: str | None = Field(
        default=None,
        title="Expand",
        description=(
            "Include additional worklog data in the response using Jira's resource expansion. "
            "Accepts a comma-separated list of properties to expand. "
            "Example: 'properties' returns custom worklog properties attached to each entry. "
            "See <a href='https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/#expansion' target='_blank'>Jira expansion docs</a>."
        ),
    )


class JiraWorklogSelector(Selector):
    jql: str = Field(
        default="updated >= -1w",
        title="JQL Filter",
        description=(
            "JQL to scope which issues' worklogs are fetched. "
            "Defaults to issues updated in the last week to avoid "
            "re-fetching all worklogs on every resync."
        ),
    )
    api_query_params: JiraWorklogAPIQueryParams | None = Field(
        alias="apiQueryParams",
        default=None,
        title="API Query Params",
        description="Additional query parameters for the worklog API.",
    )


class JiraWorklogResourceConfig(ResourceConfig):
    kind: Literal["worklog"] = Field(
        title="Jira Worklog",
        description="Jira worklog resource kind, representing time tracking entries on issues.",
    )
    selector: JiraWorklogSelector = Field(
        title="Worklog Selector",
        description="Selector for Jira worklog resources.",
    )


class ComponentSource(StrEnum):
    JIRA = "jira"
    COMPASS = "compass"
    AUTO = "auto"


class JiraComponentSelector(Selector):
    component_source: Literal[
        ComponentSource.JIRA,
        ComponentSource.COMPASS,
        ComponentSource.AUTO,
    ] = Field(
        alias="componentSource",
        title="Component Source",
        default=ComponentSource.JIRA,
        description=(
            "Filter by component source. "
            "'JIRA' returns standard project components, "
            "'COMPASS' returns Compass global components linked to this project, "
            "'AUTO' returns both. "
        ),
    )
    name_filter: str | None = Field(
        default=None,
        alias="nameFilter",
        title="Name Filter",
        description="Filter components by name or description prefix.",
    )


class JiraComponentResourceConfig(ResourceConfig):
    kind: Literal["component"] = Field(
        title="Jira Component",
        description="Jira component resource kind, representing components within Jira projects.",
    )
    selector: JiraComponentSelector = Field(
        title="Component Selector",
        description="Selector for Jira component resources.",
    )


class JiraPortAppConfig(PortAppConfig):
    resources: list[
        TeamResourceConfig
        | JiraIssueConfig
        | JiraProjectResourceConfig
        | JiraUserResourceConfig
        | JiraReleaseResourceConfig
        | JiraBoardResourceConfig
        | JiraSprintResourceConfig
        | JiraBacklogResourceConfig
        | JiraEpicResourceConfig
        | JiraWorklogResourceConfig
        | JiraComponentResourceConfig
    ] = Field(
        default_factory=list
    )  # type: ignore[assignment]
