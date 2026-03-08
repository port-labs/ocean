from typing import Literal
from pydantic import Field
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.core.handlers import APIPortAppConfig


class CopilotOrganizationMetricsSelector(Selector):
    use_usage_metrics: bool = Field(
        default=False,
        description="When true, uses the new Copilot Usage Metrics API.",
        alias="useUsageMetrics",
    )


class CopilotOrganizationMetricsResourceConfig(ResourceConfig):
    kind: Literal["copilot-organization-metrics"]
    selector: CopilotOrganizationMetricsSelector


class OrganizationUsageMetricsResourceConfig(ResourceConfig):
    kind: Literal["organization-usage-metrics"]
    selector: CopilotOrganizationMetricsSelector


class GithubCopilotAppConfig(PortAppConfig):
    resources: list[
        CopilotOrganizationMetricsResourceConfig
        | OrganizationUsageMetricsResourceConfig
        | ResourceConfig
    ]


class GithubCopilotIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = GithubCopilotAppConfig
