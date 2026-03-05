from pydantic import Field
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)


class CopilotOrganizationMetricsSelector(Selector):
    use_usage_metrics: bool = Field(
        default=False, description="When true, uses the new Copilot Usage Metrics API."
    )


class CopilotOrganizationMetricsResourceConfig(ResourceConfig):
    selector: CopilotOrganizationMetricsSelector


class GithubCopilotAppConfig(PortAppConfig):
    resources: list[CopilotOrganizationMetricsResourceConfig | ResourceConfig]
