from typing import Literal

from pydantic.v1 import Field

from client import ObjectKind
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration


class ProjectResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.PROJECT] = Field(
        title="LaunchDarkly Project",
        description="LaunchDarkly project resource kind.",
    )


class AuditLogResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.AUDITLOG] = Field(
        title="LaunchDarkly Audit Log",
        description="LaunchDarkly audit log resource kind.",
    )


class FeatureFlagSelector(Selector):
    summary: bool = Field(
        default=True,
        title="Summary Mode",
        description="Whether to fetch flags in summary mode (true) or with full environment details (false). Set to false to include per-environment prerequisites, targets, contextTargets, and rules.",
    )
    environments: list[str] = Field(
        default_factory=list,
        title="Environments",
        description="List of environment keys to fetch. When specified, only these environments are included. When empty with summary=false, per-environment rules/targets/prerequisites may be omitted per LaunchDarkly API behavior.",
    )


class FeatureFlagResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.FEATURE_FLAG] = Field(
        title="LaunchDarkly Feature Flag",
        description="LaunchDarkly feature flag resource kind.",
    )
    selector: FeatureFlagSelector = Field(
        default_factory=lambda: FeatureFlagSelector(query="true"),
        title="Feature Flag Selector",
        description="Selector for the LaunchDarkly feature flag resource.",
    )


class EnvironmentResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.ENVIRONMENT] = Field(
        title="LaunchDarkly Environment",
        description="LaunchDarkly environment resource kind.",
    )


class FeatureFlagStatusResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.FEATURE_FLAG_STATUS] = Field(
        title="LaunchDarkly Feature Flag Status",
        description="LaunchDarkly feature flag status resource kind.",
    )


class LaunchDarklyPortAppConfig(PortAppConfig):
    resources: list[
        ProjectResourceConfig
        | AuditLogResourceConfig
        | FeatureFlagResourceConfig
        | EnvironmentResourceConfig
        | FeatureFlagStatusResourceConfig
    ] = Field(
        default_factory=list,
    )  # type: ignore[assignment]


class LaunchDarklyIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = LaunchDarklyPortAppConfig
