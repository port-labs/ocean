from typing import List, Literal, Optional

from pydantic.v1 import Field
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from clients.literals import IssueStatusLiteral, IssueSeverityLiteral, IssueTypeLiteral


class ObjectKind:
    REPOSITORY = "repositories"
    ISSUES = "issues"
    ISSUE_GROUPS = "issue_groups"
    TEAM = "team"
    CONTAINER = "containers"


class RepositorySelector(Selector):
    include_inactive: bool = Field(
        default=False,
        alias="includeInactive",
        title="Include Inactive",
        description="Whether to include inactive repositories",
    )


class RepositoryResourceConfig(ResourceConfig):
    kind: Literal["repositories"] = Field(
        title="Aikido Repository",
        description="Aikido repository resource kind.",
    )
    selector: RepositorySelector = Field(
        title="Repository Selector",
        description="Selector for the Aikido repository resource.",
    )


class ContainerSelector(Selector):
    filter_status: Literal["all", "active", "inactive"] = Field(
        default="active",
        alias="filterStatus",
        title="Status",
        description="Filter containers by status: all, active, or inactive",
    )


class ContainerResourceConfig(ResourceConfig):
    kind: Literal["containers"] = Field(
        title="Aikido Container",
        description="Aikido container resource kind.",
    )
    selector: ContainerSelector = Field(
        title="Container Selector",
        description="Selector for the Aikido container resource.",
    )


class IssueSelector(Selector):
    filter_status: IssueStatusLiteral = Field(
        default="all",
        alias="filterStatus",
        title="Status",
        description="Filter issues by status.",
    )
    filter_severities: Optional[List[IssueSeverityLiteral]] = Field(
        default=None,
        alias="filterSeverities",
        title="Severities",
        description="Filter issues by one or more severities. Multiple values are combined with OR.",
    )
    filter_issue_type: Optional[IssueTypeLiteral] = Field(
        default=None,
        alias="filterIssueType",
        title="Issue type",
        description="Filter issues by type.",
    )


class IssueResourceConfig(ResourceConfig):
    kind: Literal["issues"] = Field(
        title="Aikido Issue",
        description="Aikido issue resource kind.",
    )
    selector: IssueSelector = Field(
        title="Issue Selector",
        description="Selector for the Aikido issue resource.",
    )


class IssueGroupSelector(Selector):
    scope_to_team: bool = Field(
        default=False,
        alias="scopeToTeam",
        title="Scope To Team",
        description="Whether to fetch issue groups scoped per active team. When true, each issue group is enriched with <code>__team_id</code> and <code>__team_name</code> fields, which can be used to populate the <code>aikidoTeam</code> relation on the <code>aikidoIssueGroup</code> blueprint.",
    )


class IssueGroupResourceConfig(ResourceConfig):
    kind: Literal["issue_groups"] = Field(
        title="Aikido Issue Group",
        description="Aikido issue group resource kind.",
    )
    selector: IssueGroupSelector = Field(
        title="Issue Group Selector",
        description="Selector for the Aikido issue group resource.",
    )


class TeamResourceConfig(ResourceConfig):
    kind: Literal["team"] = Field(
        title="Aikido Team",
        description="Aikido team resource kind.",
    )


class AikidoPortAppConfig(PortAppConfig):
    resources: list[
        RepositoryResourceConfig
        | ContainerResourceConfig
        | IssueResourceConfig
        | IssueGroupResourceConfig
        | TeamResourceConfig
    ] = Field(
        default_factory=list,
        title="Resources",
        description="Resources configuration for this Port app.",
    )  # type: ignore[assignment]


class AikidoIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = AikidoPortAppConfig
