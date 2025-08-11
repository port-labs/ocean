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
    severity: Optional[list[str]] = Field(
        default=None,
        description="Filter scan results by severity level",
    )
    state: Optional[list[str]] = Field(
        default=None,
        description="Filter scan results by state",
    )
    sort: Optional[list[str]] = Field(
        default=None,
        description="Sort order for scan results",
    )
    status: Optional[list[str]] = Field(
        default=None,
        description="Filter scan results by status",
    )
    exclude_result_types: Optional[str] = Field(
        default=None,
        description="Exclude specific result types from the search",
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
