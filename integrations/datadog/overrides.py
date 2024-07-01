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
    sample_interval_period_in_days: int = Field(
        alias="sampleIntervalPeriodInDays", default=7
    )

    @validator("sample_interval_period_in_days")
    def validate_resource_kinds_min_size(cls, v: int) -> int:
        if v < 1:
            raise ValueError("sampleIntervalPeriodInDays must be greater than 0")
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
