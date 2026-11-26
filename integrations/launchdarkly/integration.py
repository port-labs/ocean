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


class FeatureFlagResourceConfig(ResourceConfig):
    class FeatureFlagSelector(Selector):
        include_environment_config: bool = Field(
            alias="includeEnvironmentConfig",
            default=False,
            title="Include Environment Configuration",
            description=(
                "If set to true, flags are fetched with summary=0 for every "
                "environment of the project, so each flag's `environments` object "
                "contains the full targeting configuration (on, rules, targets, "
                "contextTargets, prerequisites, fallthrough, offVariation). "
                "This increases the payload size. Default value is false."
            ),
        )

    kind: Literal[ObjectKind.FEATURE_FLAG] = Field(
        title="LaunchDarkly Feature Flag",
        description="LaunchDarkly feature flag resource kind.",
    )
    selector: FeatureFlagSelector = Field(
        title="LaunchDarkly Feature Flag Selector",
        description="Configuration for fetching LaunchDarkly feature flags synced into Port.",
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
