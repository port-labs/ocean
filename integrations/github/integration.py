from typing import Literal
from pydantic import Field
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.integrations.base import BaseIntegration


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
        | ResourceConfig
    ]


class GithubIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = GithubPortAppConfig
