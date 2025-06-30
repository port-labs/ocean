from typing import Literal
from pydantic import BaseModel, Field
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.integrations.base import BaseIntegration

from github.helpers.utils import ObjectKind


class RepositoryBranchMapping(BaseModel):
    name: str = Field(
        description="Specify the repository name",
    )
    branch: str = Field(
        default="",
        description="Specify the branch to bring the folders from, repo's default branch will be used if none is passed",
    )


class FolderSelector(BaseModel):
    path: str = Field(default="*")
    repos: list[RepositoryBranchMapping]


class GithubFolderSelector(Selector):
    folders: list[FolderSelector]


class GithubFolderResourceConfig(ResourceConfig):
    selector: GithubFolderSelector
    kind: Literal[ObjectKind.FOLDER]


class GithubPullRequestSelector(Selector):
    state: Literal["open", "closed", "all"] = Field(
        default="open",
        description="Filter by pull request state (e.g., open, closed, all)",
    )


class GithubPullRequestConfig(ResourceConfig):
    selector: GithubPullRequestSelector
    kind: Literal["pull-request"]


class GithubIssueSelector(Selector):
    state: Literal["open", "closed", "all"] = Field(
        default="open",
        description="Filter by issue state (open, closed, all)",
    )


class GithubIssueConfig(ResourceConfig):
    selector: GithubIssueSelector
    kind: Literal["issue"]


class GithubTeamSector(Selector):
    members: bool = Field(default=True)


class GithubTeamConfig(ResourceConfig):
    selector: GithubTeamSector
    kind: Literal[ObjectKind.TEAM]


class GithubDependabotAlertSelector(Selector):
    states: list[Literal["auto_dismissed", "dismissed", "fixed", "open"]] = Field(
        default=["open"],
        description="Filter alerts by state (auto_dismissed, dismissed, fixed, open)",
    )


class GithubDependabotAlertConfig(ResourceConfig):
    selector: GithubDependabotAlertSelector
    kind: Literal["dependabot-alert"]


class GithubCodeScanningAlertSelector(Selector):
    state: Literal["open", "closed", "dismissed", "fixed"] = Field(
        default="open",
        description="Filter alerts by state (open, closed, dismissed, fixed)",
    )


class GithubCodeScanningAlertConfig(ResourceConfig):
    selector: GithubCodeScanningAlertSelector
    kind: Literal["code-scanning-alerts"]


class GithubPortAppConfig(PortAppConfig):
    repository_type: str = Field(alias="repositoryType", default="all")
    resources: list[
        GithubPullRequestConfig
        | GithubIssueConfig
        | GithubDependabotAlertConfig
        | GithubCodeScanningAlertConfig
        | GithubFolderResourceConfig
        | GithubTeamConfig
        | ResourceConfig
    ]


class GithubIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = GithubPortAppConfig
