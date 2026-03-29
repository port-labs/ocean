from typing import Optional, Literal

from loguru import logger
from port_ocean.core.handlers import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortAppConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from pydantic import Field, validator, BaseModel


class SLOHistorySelector(Selector):
    timeframe: int = Field(
        alias="timeframe",
        default=7,
        title="Timeframe",
        description="Time window in days for each SLO history data point.",
    )
    period_of_time_in_months: int = Field(
        alias="periodOfTimeInMonths",
        default=12,
        title="Period of Time in Months",
        description="How far back in time to fetch SLO history (1-12 months).",
    )
    period_of_time_in_days: Optional[int] = Field(
        alias="periodOfTimeInDays",
        default=None,
        title="Period of Time in Days",
        description="How far back in time to fetch SLO history in days (1-365).",
    )
    concurrency: int = Field(
        alias="concurrency",
        default=2,
        title="Concurrency",
        description="Number of concurrent requests to make to Datadog.",
    )

    @validator("timeframe")
    def validate_timeframe_field(cls, v: int) -> int:
        if v < 1:
            logger.warning(
                f"The selector value 'timeframe' ({v}) must be greater than 0. "
                f"This value determines the time window in days for each SLO history data point. "
                f"Using default value of 7 days."
            )
            return 7
        return v

    @validator("period_of_time_in_months")
    def validate_period_of_time_in_months(cls, v: int) -> int:
        if v < 1 or v > 12:
            logger.warning(
                f"The selector value 'periodOfTimeInMonths' ({v}) must be between 1 and 12. "
                f"This value determines how far back in time to fetch SLO history. "
                f"Using default value of 6 months."
            )
            return 6
        return v

    @validator("period_of_time_in_days")
    def validate_period_of_time_in_days(cls, v: int) -> int:
        if v < 1 or v > 365:
            logger.warning(
                f"The selector value 'periodOfTimeInDays' ({v}) must be between 1 and 365. "
                f"This value determines how far back in time to fetch SLO history. "
                f"Using default value of 7 days."
            )
            return 7
        return v

    @validator("concurrency")
    def validate_concurrency(cls, v: int) -> int:
        if v < 1:
            logger.warning(
                f"The selector value 'concurrency' ({v}) must be larger than 0. "
                f"This value determines how many concurrent requests to make to Datadog. "
                f"Using default value of 2."
            )
            return 2
        return v


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


class DatadogSelector(BaseModel):
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
    )


class DatadogResourceSelector(Selector):
    datadog_selector: DatadogSelector = Field(
        alias="datadogSelector",
        title="Datadog Selector",
        description="Datadog metric query configuration.",
    )


class DatadogResourceConfig(ResourceConfig):
    kind: Literal["serviceMetric"] = Field(
        title="Datadog Service Metric",
        description="Datadog service metric resource kind.",
    )
    selector: DatadogResourceSelector = Field(
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


class MonitorResourceConfig(ResourceConfig):
    kind: Literal["monitor"] = Field(
        title="Datadog Monitor",
        description="Datadog monitor resource kind.",
    )


class SLOResourceConfig(ResourceConfig):
    kind: Literal["slo"] = Field(
        title="Datadog SLO",
        description="Datadog SLO resource kind.",
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


class DataDogPortAppConfig(PortAppConfig):
    resources: list[
        ServiceDependencyResourceConfig
        | TeamResourceConfig
        | SLOHistoryResourceConfig
        | DatadogResourceConfig
        | HostResourceConfig
        | MonitorResourceConfig
        | SLOResourceConfig
        | ServiceResourceConfig
        | UserResourceConfig
    ] = Field(
        default_factory=list,
        alias="resources",
        title="Resources",
        description="Specify the resources to include in the sync process",
    )  # type: ignore[assignment]


class DatadogIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = DataDogPortAppConfig
