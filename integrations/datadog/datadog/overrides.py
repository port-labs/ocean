from typing import Optional, Literal

from port_ocean.core.handlers import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortAppConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from pydantic import Field, BaseModel


class SLOHistorySelector(Selector):
    timeframe: int = Field(
        alias="timeframe",
        default=7,
        title="Timeframe",
        description="Time window in days for each SLO history data point.",
        ge=1,
    )
    period_of_time_in_months: int = Field(
        alias="periodOfTimeInMonths",
        default=12,
        title="Period of Time in Months",
        description="How far back in time to fetch SLO history (1-12 months).",
        ge=1,
        le=12,
    )
    period_of_time_in_days: Optional[int] = Field(
        alias="periodOfTimeInDays",
        default=None,
        title="Period of Time in Days",
        description="How far back in time to fetch SLO history in days (1-365).",
        ge=1,
        le=365,
    )
    concurrency: int = Field(
        alias="concurrency",
        default=50,
        title="Concurrency",
        description=(
            "Number of concurrent requests to make to Datadog. "
            "Increasing this value speeds up data sync but risks hitting API rate limits. "
        ),
        ge=1,
    )


class SLOHistoryResourceConfig(ResourceConfig):
    kind: Literal["sloHistory"] = Field(
        title="Datadog SLO History",
        description="Datadog SLO history resource kind.",
    )
    selector: SLOHistorySelector = Field(
        title="SLO History Selector",
        description="Selector for the Datadog SLO history resource.",
    )


class DatadogMetricSelector(BaseModel):
    tag: str = Field(
        alias="tag",
        title="Tag",
        description="The tag key to filter metrics by.",
    )
    value: str = Field(
        alias="value",
        default="*",
        title="Value",
        description="The tag value to filter metrics by.",
    )


class ServiceMetricSelector(BaseModel):
    metric: str = Field(
        alias="metric",
        title="Metric",
        description="The Datadog metric query to fetch.",
    )
    env: DatadogMetricSelector = Field(
        alias="env",
        title="Environment",
        description="Environment tag filter for the metric.",
    )
    service: DatadogMetricSelector = Field(
        alias="service",
        title="Service",
        description="Service tag filter for the metric.",
    )
    timeframe: int = Field(
        alias="timeframe",
        default=1,
        title="Timeframe",
        description="Time frame in minutes for the metric query.",
        ge=1,
    )


class ServiceMetricResourceSelector(Selector):
    metric_selector: ServiceMetricSelector = Field(
        alias="datadogSelector",
        title="Datadog Selector",
        description="Datadog metric query configuration.",
    )


class ServiceMetricResourceConfig(ResourceConfig):
    kind: Literal["serviceMetric"] = Field(
        title="Datadog Service Metric",
        description="Datadog service metric resource kind.",
    )
    selector: ServiceMetricResourceSelector = Field(
        title="Service Metric Selector",
        description="Selector for the Datadog service metric resource.",
    )


class TeamSelector(Selector):
    include_members: bool = Field(
        alias="includeMembers",
        default=False,
        title="Include Members",
        description="Whether to include the members of the team, defaults to false",
    )


class TeamResourceConfig(ResourceConfig):
    kind: Literal["team"] = Field(
        title="Datadog Team",
        description="Datadog team resource kind.",
    )
    selector: TeamSelector = Field(
        title="Team Selector",
        description="Selector for the Datadog team resource.",
    )


class DatadogServiceDependencySelector(Selector):
    start_time: float = Field(
        default=1,
        title="Start Time",
        description="Specify the start time to fetch the service dependencies in hours, defaults to last 1 hour",
        alias="startTime",
    )
    environment: str = Field(
        default="prod",
        title="Environment",
        description="Specify the service dependency environment, defaults to 'prod'",
        alias="environment",
    )


class ServiceDependencyResourceConfig(ResourceConfig):
    kind: Literal["serviceDependency"] = Field(
        title="Datadog Service Dependency",
        description="Datadog service dependency resource kind.",
    )
    selector: DatadogServiceDependencySelector = Field(
        title="Service Dependency Selector",
        description="Selector for the Datadog service dependency resource.",
    )


class HostResourceConfig(ResourceConfig):
    kind: Literal["host"] = Field(
        title="Datadog Host",
        description="Datadog host resource kind.",
    )


class MonitorSelector(Selector):
    include_restriction_policy: bool = Field(
        alias="includeRestrictionPolicy",
        default=False,
        title="Include Restriction Policy",
        description="Whether to enrich each monitor with its restriction policy, defaults to false",
    )


class MonitorResourceConfig(ResourceConfig):
    kind: Literal["monitor"] = Field(
        title="Datadog Monitor",
        description="Datadog monitor resource kind.",
    )
    selector: MonitorSelector = Field(
        title="Monitor Selector",
        description="Selector for the Datadog monitor resource.",
    )


class SLOSelector(Selector):
    include_restriction_policy: bool = Field(
        alias="includeRestrictionPolicy",
        default=False,
        title="Include Restriction Policy",
        description="Whether to enrich each SLO with its restriction policy, defaults to false",
    )


class SLOResourceConfig(ResourceConfig):
    kind: Literal["slo"] = Field(
        title="Datadog SLO",
        description="Datadog SLO resource kind.",
    )
    selector: SLOSelector = Field(
        title="SLO Selector",
        description="Selector for the Datadog SLO resource.",
    )


class ServiceResourceConfig(ResourceConfig):
    kind: Literal["service"] = Field(
        title="Datadog Service",
        description="Datadog service resource kind.",
    )


class UserResourceConfig(ResourceConfig):
    kind: Literal["user"] = Field(
        title="Datadog User",
        description="Datadog user resource kind.",
    )


class RoleSelector(Selector):
    include_users: bool = Field(
        default=False,
        alias="includeUsers",
        title="Enrich roles with users",
        description="When enabled, each role is enriched with the list of users assigned to it, available under the `__users` property. Enabling this makes an additional API request per role, which may slow down the resync.",
    )


class RoleResourceConfig(ResourceConfig):
    kind: Literal["role"] = Field(
        title="Datadog Role",
        description="Datadog role resource kind.",
    )
    selector: RoleSelector = Field(
        title="Datadog Selector", description="Selector for Datadog roles."
    )


class DataDogPortAppConfig(PortAppConfig):
    resources: list[
        ServiceDependencyResourceConfig
        | TeamResourceConfig
        | SLOHistoryResourceConfig
        | ServiceMetricResourceConfig
        | HostResourceConfig
        | MonitorResourceConfig
        | SLOResourceConfig
        | ServiceResourceConfig
        | UserResourceConfig
        | RoleResourceConfig
    ] = Field(
        default_factory=list,
        alias="resources",
        title="Resources",
        description="Specify the resources to include in the sync process",
    )  # type: ignore[assignment]


class DatadogIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = DataDogPortAppConfig
