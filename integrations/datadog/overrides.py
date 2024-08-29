import typing

from port_ocean.core.handlers import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortAppConfig,
    Selector,
)
from pydantic import Field, validator, BaseModel

from port_ocean.core.integrations.base import BaseIntegration


class SLOHistorySelector(Selector):
    timeframe: int = Field(alias="timeframe", default=7)
    period_of_time_in_months: int = Field(alias="periodOfTimeInMonths", default=12)

    @validator("timeframe")
    def validate_timeframe_field(cls, v: int) -> int:
        if v < 1:
            raise ValueError("timeframe must be greater than 0")
        return v

    @validator("period_of_time_in_months")
    def validate_period_of_time_in_years(cls, v: int) -> int:
        if v > 1:
            raise ValueError("period_of_time_in_months must be less or equal to 12")
        return v


class SLOHistoryResourceConfig(ResourceConfig):
    kind: typing.Literal["sloHistory"]
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


class DataDogPortAppConfig(PortAppConfig):
    resources: list[
        SLOHistoryResourceConfig | DatadogResourceConfig | ResourceConfig
    ] = Field(default_factory=list)


class DatadogIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = DataDogPortAppConfig
