import typing

from port_ocean.core.handlers import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortAppConfig,
    Selector,
)
from pydantic import Field, validator

from port_ocean.core.integrations.base import BaseIntegration


class IssueSelector(Selector):
    limit: int = Field(alias="limit", default=500)

    @validator("limit")
    def validate_limit_field(cls, v: int) -> int:
        if v < 1:
            raise ValueError("limit must be greater than 0")
        return v


class IssueResourceConfig(ResourceConfig):
    kind: typing.Literal["sloHistory"]
    selector: IssueSelector


class WizPortAppConfig(PortAppConfig):
    resources: list[IssueResourceConfig | ResourceConfig] = Field(
        default_factory=list
    )


class WizIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = WizPortAppConfig
