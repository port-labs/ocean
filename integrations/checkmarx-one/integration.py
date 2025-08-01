from typing import Literal, Optional

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from pydantic import Field


class CheckmarxOneResultSelector(Selector):
    limit: Optional[int] = Field(
        default=None,
        description="Limit search to component names that contain the supplied string",
    )
    offset: Optional[int] = Field(
        default=None,
        description="Limit search to component names that contain the supplied string",
    )
    severity: Optional[str] = Field(
        default=None,
        description="Limit search to component names that contain the supplied string",
    )
    state: Optional[str] = Field(
        default=None,
        description="Limit search to component names that contain the supplied string",
    )
    sort: Optional[str] = Field(
        default=None,
        description="Limit search to component names that contain the supplied string",
    )
    status: Optional[str] = Field(
        default=None,
        description="Limit search to component names that contain the supplied string",
    )
    exclude_result_types: Optional[str] = Field(
        default=None,
        description="Limit search to component names that contain the supplied string",
    )


class CheckmarxOneScanResultResourcesConfig(ResourceConfig):
    kind: Literal["scan_result"]
    selector: CheckmarxOneResultSelector


class CheckmarxOneScanSelector(Selector):
    project_ids: list[str] = Field(
        default_factory=list,
        alias="projectIds",
        description="Limit search to specific project IDs",
    )
    limit: int = Field(
        default=None,
        description="Limit the number of results returned",
    )
    offset: int = Field(
        default=None,
        description="Offset for pagination",
    )


class CheckmarxOneScanResourcesConfig(ResourceConfig):
    kind: Literal["scan"]
    selector: CheckmarxOneScanSelector


class CheckmarxOnePortAppConfig(PortAppConfig):
    resources: list[
        CheckmarxOneScanResultResourcesConfig
        | CheckmarxOneScanResourcesConfig
        | ResourceConfig
    ]


class CheckmarxOneIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = CheckmarxOnePortAppConfig
