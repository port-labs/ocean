from typing import Literal

from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from pydantic import Field

from client.client import GithubState, GithubRepositoryTypes
from utils import ObjectKind


class RepositorySelector(Selector):
    repo_type: GithubRepositoryTypes = Field(
        alias="repoType",
        description="Type of repository to retrieve",
        default=GithubRepositoryTypes.ALL,
    )


class PullRequestSelector(Selector):
    state: GithubState = Field(
        description="State of pull request", default=GithubState.ALL
    )
    repo_type: GithubRepositoryTypes = Field(
        description="The type of repository we want to get PRs from",
        default=GithubRepositoryTypes.ALL,
        alias="repoType",
    )


class IssueSelector(Selector):
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
    repo_type: GithubRepositoryTypes = Field(
        description="The type of repository we want to get issues from",
        default=GithubRepositoryTypes.ALL,
        alias="repoType",
    )


class GithubRepositoryResourceConfig(ResourceConfig):
    selector: RepositorySelector
    kind: Literal[ObjectKind.REPO]


class GithubPullRequestResourceConfig(ResourceConfig):
    selector: PullRequestSelector
    kind: Literal[ObjectKind.PR]


class GithubIssueResourceConfig(ResourceConfig):
    selector: IssueSelector
    kind: Literal[ObjectKind.ISSUE]


class GithubWorkflowResourceConfig(ResourceConfig):
    selector: WorkflowSelector
    kind: Literal[ObjectKind.WORKFLOW]


class GithubPortAppConfig(PortAppConfig):
    resources: list[
        GithubIssueResourceConfig
        | GithubPullRequestResourceConfig
        | GithubRepositoryResourceConfig
        | GithubWorkflowResourceConfig
        | ResourceConfig
    ] = []


class GithubIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = GithubPortAppConfig
