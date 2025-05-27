from pydantic import Field
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.integrations.base import BaseIntegration
from typing import Literal, Optional, List


class GithubDependabotAlertSelector(Selector):
    state: Optional[List[str]] = Field(
        default=None,
        description="Filter alerts by state (auto_dismissed, dismissed, fixed, open)"
    )
    severity: Optional[List[str]] = Field(
        default=None,
        description="Filter alerts by severity (low, medium, high, critical)"
    )
    ecosystem: Optional[List[str]] = Field(
        default=None,
        description="Filter alerts by ecosystem (composer, go, maven, npm, nuget, pip, pub, rubygems, rust)"
    )
    scope: Optional[str] = Field(
        default=None,
        description="Filter alerts by scope (development, runtime)"
    )

class GithubDependabotAlertConfig(ResourceConfig):
    selector: GithubDependabotAlertSelector
    kind: Literal["dependabot-alert"]


class GithubCodeScanningAlertSelector(Selector):
    tool_name: Optional[List[str]] = Field(
        default=None,
        description="Filter alerts by tool name (e.g., CodeQL, GitHub Advanced Security)"
    )

class GithubCodeScanningAlertConfig(ResourceConfig):
    selector: GithubCodeScanningAlertSelector
    kind: Literal["code-scanning-alerts"]


class GithubPortAppConfig(PortAppConfig):
    repository_visibility_filter: str = Field(
        alias="repositoryVisibilityFilter", default="all"
    )
    resources: list[GithubDependabotAlertConfig | GithubCodeScanningAlertConfig | ResourceConfig]


class GithubIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = GithubPortAppConfig
