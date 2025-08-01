from typing import Literal

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from pydantic.fields import Field


class CheckmarxOneResultSelector(Selector):
    limit: int | None = Field(
        description="Limit search to component names that contain the supplied string"
    )
    offset: int | None = Field(
        description="Limit search to component names that contain the supplied string"
    )
    severity: str | None = Field(
        description="Limit search to component names that contain the supplied string"
    )
    state: str | None = Field(
        description="Limit search to component names that contain the supplied string"
    )
    sort: str | None = Field(
        description="Limit search to component names that contain the supplied string"
    )
    status: str | None = Field(
        description="Limit search to component names that contain the supplied string"
    )
    exclude_result_types: str | None = Field(
        description="Limit search to component names that contain the supplied string"
    )


class CheckmarxOneResultResourcesConfig(ResourceConfig):
    kind: Literal["scan_result"] = "scan_result"
    selector: CheckmarxOneResultSelector = CheckmarxOneResultSelector


class CheckmarxOneScanSelector(Selector):
    project_ids: list[str] | None = Field(
        description="Limit search to specific project IDs",
        default_factory=list,
        alias="projectids",
    )
    limit: int | None = Field(
        description="Limit the number of results returned", default=None
    )
    offset: int | None = Field(description="Offset for pagination", default=None)


class CheckmarxOneScanResourcesConfig(ResourceConfig):
    kind: Literal["scan"]
    selector: CheckmarxOneScanSelector


class CheckmarxOnePortAppConfig(PortAppConfig):
    resources: list[
        CheckmarxOneScanResourcesConfig
        | CheckmarxOneResultResourcesConfig
        | ResourceConfig
    ]


class CheckmarxOneIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = CheckmarxOnePortAppConfig
