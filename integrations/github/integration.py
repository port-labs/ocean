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
    state: List[str] = Field(
        default=["open"],
        description="Filter alerts by state (open, closed, dismissed, fixed)"
    )


class GithubDependabotAlertConfig(ResourceConfig):
    selector: GithubDependabotAlertSelector
    kind: Literal["dependabot-alert"]


class GithubCodeScanningAlertSelector(Selector):
    state: List[str] = Field(
        default=["open"],
        description="Filter alerts by state (open, closed, dismissed, fixed)"
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
