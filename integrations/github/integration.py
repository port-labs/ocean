from typing import Literal
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from pydantic import Field

from port import PortGithubResources
from wrappers.github import GithubState, GithubRepositoryTypes


class RepositorySelector(Selector):
    orgs: list[str] = Field(
        description="list of organizations to retrieve from", default_factory=list
    )
    repo_type: GithubRepositoryTypes = Field(
        alias="repoType",
        description="Type of repository to retrieve",
        default=GithubRepositoryTypes.ALL,
    )


class PullRequestSelector(Selector):
    orgs: list[str] = Field(
        description="List of organizations to retrieve from", default_factory=list
    )
    state: GithubState = Field(
        description="State of pull request", default=GithubState.ALL
    )
    repo_type: GithubRepositoryTypes = Field(
        description="The type of repository we want to get PRs from",
        default=GithubRepositoryTypes.ALL,
        alias="repoType",
    )


class IssueSelector(Selector):
    orgs: list[str] = Field(
        description="List of organizations to retrieve from", default_factory=list
    )
    state: GithubState = Field(
        description="state of the issues you want to fetch",
        default=GithubState.ALL,
    )
    repo_type: GithubRepositoryTypes = Field(
        description="The type of repository we want to get issues from",
        default=GithubRepositoryTypes.ALL,
        alias="repoType",
    )


class WorkflowSelector(Selector):
    orgs: list[str] = Field(
        description="List of organizations to retrieve from", default_factory=list
    )
    repo_type: GithubRepositoryTypes = Field(
        description="The type of repository we want to get issues from",
        default=GithubRepositoryTypes.ALL,
        alias="repoType",
    )


class TeamSelector(Selector):
    orgs: list[str] = Field(
        description="List of organizations to retrieve from", default_factory=list
    )


class GithubRepositoryResourceConfig(ResourceConfig):
    selector: RepositorySelector
    kind: Literal[PortGithubResources.REPO]


class GithubPullRequestResourceConfig(ResourceConfig):
    selector: PullRequestSelector
    kind: Literal[PortGithubResources.PR]


class GithubIssueResourceConfig(ResourceConfig):
    selector: IssueSelector
    kind: Literal[PortGithubResources.ISSUE]


class GithubWorkflowResourceConfig(ResourceConfig):
    selector: WorkflowSelector
    kind: Literal[PortGithubResources.WORKFLOW]


class GithubTeamResourceConfig(ResourceConfig):
    selector: TeamSelector
    kind: Literal[PortGithubResources.TEAM]


class GithubPortAppConfig(PortAppConfig):
    resources: list[
        GithubIssueResourceConfig
        | GithubPullRequestResourceConfig
        | GithubRepositoryResourceConfig
        | GithubWorkflowResourceConfig
        | GithubTeamResourceConfig
        | ResourceConfig
    ] = []


class GithubIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = GithubPortAppConfig
