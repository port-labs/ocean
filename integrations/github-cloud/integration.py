from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from pydantic import Field
from typing import Literal
from enum import StrEnum


class ObjectKind(StrEnum):
    ORGANIZATION = "organization"
    REPOSITORY = "repository"
    ISSUE = "issue"
    PULL_REQUEST = "pull_request"
    TEAM = "team"
    WORKFLOW = "workflow"


class OrganizationSelector(Selector):
    """Selector for GitHub organizations."""

    organizations: list[str] = Field(
        default_factory=list, description="List of organization names to filter"
    )


class RepositorySelector(Selector):
    """Selector for GitHub repositories."""

    organizations: list[str] = Field(
        default_factory=list,
        description="List of organization names to filter repositories",
    )
    visibility: str = Field(
        default="all", description="Repository visibility (all, public, private)"
    )


class IssueSelector(Selector):
    """Selector for GitHub issues."""

    organizations: list[str] = Field(
        default_factory=list, description="List of organization names to filter issues"
    )
    state: str = Field(default="all", description="Issue state (all, open, closed)")


class PullRequestSelector(Selector):
    """Selector for GitHub pull requests."""

    organizations: list[str] = Field(
        default_factory=list,
        description="List of organization names to filter pull requests",
    )
    state: str = Field(
        default="all", description="Pull request state (all, open, closed, merged)"
    )


class TeamSelector(Selector):
    """Selector for GitHub teams."""

    organizations: list[str] = Field(
        default_factory=list, description="List of organization names to filter teams"
    )


class WorkflowSelector(Selector):
    """Selector for GitHub workflows."""

    organizations: list[str] = Field(
        default_factory=list,
        description="List of organization names to filter workflows",
    )
    state: str = Field(
        default="active", description="Workflow state (active, disabled)"
    )


class OrganizationResourceConfig(ResourceConfig):
    selector: OrganizationSelector
    kind: Literal["organization"]


class RepositoryResourceConfig(ResourceConfig):
    selector: RepositorySelector
    kind: Literal["repository"]


class IssueResourceConfig(ResourceConfig):
    selector: IssueSelector
    kind: Literal["issue"]


class PullRequestResourceConfig(ResourceConfig):
    selector: PullRequestSelector
    kind: Literal["pull_request"]


class TeamResourceConfig(ResourceConfig):
    selector: TeamSelector
    kind: Literal["team"]


class WorkflowResourceConfig(ResourceConfig):
    selector: WorkflowSelector
    kind: Literal["workflow"]


class GitHubPortAppConfig(PortAppConfig):
    """Configuration for GitHub Cloud integration."""

    resources: list[
        OrganizationResourceConfig
        | RepositoryResourceConfig
        | IssueResourceConfig
        | PullRequestResourceConfig
        | TeamResourceConfig
        | WorkflowResourceConfig
    ] = Field(default_factory=list, description="List of resources to sync from GitHub")


class GitHubCloudIntegration(BaseIntegration):
    """GitHub Cloud integration for Port Ocean.

    This integration provides functionality to sync GitHub resources including:
    - Repositories
    - Issues
    - Pull Requests
    - Teams
    - Workflows
    """

    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = GitHubPortAppConfig
