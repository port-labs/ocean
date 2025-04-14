from typing import Literal
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from pydantic import Field


class GitHubIssueSelector(Selector):
    query: str | None = Field(
        default=None,
        description="Optional query or filter expression for GitHub issues (e.g. 'state:open')."
    )

class GitHubIssueConfig(ResourceConfig):
    selector: GitHubIssueSelector
    kind: Literal["issue"]


class GitHubRepoSelector(Selector):
    includeArchived: bool = Field(
        alias="includeArchived",
        default=False,
        description="Whether to include archived repositories; defaults to false."
    )

class GitHubRepoConfig(ResourceConfig):
    selector: GitHubRepoSelector
    kind: Literal["repository"]


class GitHubPullRequestSelector(Selector):
    state: Literal["open", "closed", "all"] = Field(
        default="open",
        description="Filter pull requests by state."
    )

class GitHubPullRequestConfig(ResourceConfig):
    selector: GitHubPullRequestSelector
    kind: Literal["pull-request"]


class GitHubTeamSelector(Selector):
    includeMembers: bool = Field(
        alias="includeMembers",
        default=False,
        description="Whether to include the members of the team; defaults to false."
    )

class GitHubTeamConfig(ResourceConfig):
    selector: GitHubTeamSelector
    kind: Literal["team"]


class GitHubWorkflowSelector(Selector):
    state: Literal["active", "disabled", "all"] = Field(
        default="active",
        description="Filter workflows by their state."
    )

class GitHubWorkflowConfig(ResourceConfig):
    selector: GitHubWorkflowSelector
    kind: Literal["workflow"]




class GitHubPortAppConfig(PortAppConfig):
    resources: list[
        GitHubRepoConfig
        | GitHubIssueConfig
        | GitHubPullRequestConfig
        | GitHubTeamConfig
        | GitHubWorkflowConfig
        | ResourceConfig  # Fallback for additional resource configurations
    ]
