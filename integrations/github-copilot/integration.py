from typing import Literal

from pydantic import Field

from kinds import ObjectKind
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
)
from port_ocean.core.integrations.base import BaseIntegration


class CopilotTeamMetricsResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.COPILOT_TEAM_METRICS] = Field(
        title="GitHub Copilot Team Metrics",
        description="GitHub Copilot team metrics resource kind.",
    )


class CopilotOrganizationMetricsResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.COPILOT_ORGANIZATION_METRICS] = Field(
        title="GitHub Copilot Organization Metrics",
        description="GitHub Copilot organization metrics resource kind.",
    )


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
        CopilotTeamMetricsResourceConfig
        | CopilotOrganizationMetricsResourceConfig
        | OrganizationUsageMetricsResourceConfig
        | UserUsageMetricsResourceConfig
    ] = Field(
        default_factory=list,
    )  # type: ignore[assignment]


class GithubCopilotIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = GithubCopilotPortAppConfig
