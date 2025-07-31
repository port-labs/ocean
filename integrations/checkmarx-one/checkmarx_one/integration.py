from typing import Annotated, Literal, Union

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from pydantic.fields import Field


class CheckmarxOneScanSelector(Selector):
    project_ids: list[str] | None = Field(description="Limit search to specific project IDs")
    limit: int | None = Field(description="Limit the number of results returned")
    offset: int | None = Field(description="Offset for pagination")


class CheckmarxOneScanResourcesConfig(ResourceConfig):
    kind: Literal["scan"] = "scan"
    selector: CheckmarxOneScanSelector = CheckmarxOneScanSelector

CheckmarxResourcesConfig = Annotated[
    Union[
        CheckmarxOneScanResourcesConfig,
        ResourceConfig,
    ],
    Field(discriminator="kind"),
]

class CheckmarxOnePortAppConfig(PortAppConfig):
    resources: Union[CheckmarxResourcesConfig] = Field(default_factory=list)


class CheckmarxOneIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = CheckmarxOnePortAppConfig
