from typing import Literal
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
)
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.core.handlers import APIPortAppConfig


class CopilotOrganizationMetricsResourceConfig(ResourceConfig):
    kind: Literal["copilot-organization-metrics"]


class OrganizationUsageMetricsResourceConfig(ResourceConfig):
    kind: Literal["organization-usage-metrics"]


class GithubCopilotAppConfig(PortAppConfig):
    resources: list[
        CopilotOrganizationMetricsResourceConfig
        | OrganizationUsageMetricsResourceConfig
        | ResourceConfig
    ]


class GithubCopilotIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = GithubCopilotAppConfig
