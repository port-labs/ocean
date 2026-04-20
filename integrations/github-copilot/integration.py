from typing import Literal

from pydantic import Field


from port_ocean.core.handlers import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
)
from port_ocean.core.integrations.base import BaseIntegration

from kinds import ObjectKind


class OrganizationUsageMetricsResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.ORGANIZATION_USAGE_METRICS] = Field(
        title="GitHub Copilot Organization Usage Metrics",
        description="GitHub Copilot organization usage metrics resource kind.",
    )


class UserUsageMetricsResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.USER_USAGE_METRICS] = Field(
        title="GitHub Copilot User Usage Metrics",
        description="GitHub Copilot user usage metrics resource kind.",
    )


class GithubCopilotPortAppConfig(PortAppConfig):
    resources: list[
        OrganizationUsageMetricsResourceConfig | UserUsageMetricsResourceConfig
    ] = Field(
        default_factory=list,
    )  # type: ignore[assignment]


class GithubCopilotIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = GithubCopilotPortAppConfig
