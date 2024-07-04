import typing

from port_ocean.core.handlers import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortAppConfig,
    Selector,
)
from pydantic import Field, validator

from port_ocean.core.integrations.base import BaseIntegration


class SLOHistorySelector(Selector):
    timeframe: int = Field(alias="timeframe", default=7)
    period_of_time_in_years: int = Field(alias="periodOfTimeInYears", default=1)

    @validator("timeframe")
    def validate_timeframe_field(cls, v: int) -> int:
        if v < 1:
            raise ValueError("timeframe must be greater than 0")
        return v

    @validator("period_of_time_in_years")
    def validate_period_of_time_in_years(cls, v: int) -> int:
        if v > 1:
            raise ValueError("period_of_time_in_years must be less than 1")
        return v


class SLOHistoryResourceConfig(ResourceConfig):
    kind: typing.Literal["sloHistory"]
    selector: SLOHistorySelector


class DataDogPortAppConfig(PortAppConfig):
    resources: list[SLOHistoryResourceConfig | ResourceConfig] = Field(
        default_factory=list
    )


class DatadogIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = DataDogPortAppConfig
