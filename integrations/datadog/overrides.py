from typing import Optional, Literal

from port_ocean.core.handlers import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortAppConfig,
    Selector,
)
from pydantic import Field, validator, BaseModel
from loguru import logger
from port_ocean.core.integrations.base import BaseIntegration


class SLOHistorySelector(Selector):
    timeframe: int = Field(alias="timeframe", default=7)
    period_of_time_in_months: int = Field(alias="periodOfTimeInMonths", default=12)
    period_of_time_in_days: Optional[int] = Field(alias="periodOfTimeInDays")
    concurrency: int = Field(alias="concurrency", default=2)

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
    kind: Literal["sloHistory"]
    selector: SLOHistorySelector


class DatadogMetricSelector(BaseModel):
    tag: str = Field(alias="tag", required=True)
    value: str = Field(alias="value", default="*")


class DatadogSelector(BaseModel):
    metric: str = Field(alias="metric", required=True)
    env: DatadogMetricSelector = Field(alias="env")
    service: DatadogMetricSelector = Field(alias="service")
    timeframe: int = Field(
        alias="timeframe", description="Time frame in minutes", default=1
    )


class DatadogResourceSelector(Selector):
    datadog_selector: DatadogSelector = Field(alias="datadogSelector")


class DatadogResourceConfig(ResourceConfig):
    selector: DatadogResourceSelector


class TeamSelector(Selector):
    include_members: bool = Field(
        alias="includeMembers",
        default=False,
        description="Whether to include the members of the team, defaults to false",
    )


class TeamResourceConfig(ResourceConfig):
    kind: Literal["team"]
    selector: TeamSelector


class DataDogPortAppConfig(PortAppConfig):
    resources: list[
        TeamResourceConfig
        | SLOHistoryResourceConfig
        | DatadogResourceConfig
        | ResourceConfig
    ] = Field(default_factory=list)


class DatadogIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = DataDogPortAppConfig
