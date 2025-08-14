from typing import Literal, Optional, List

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from pydantic import Field


class CheckmarxOneResultSelector(Selector):
    severity: Optional[List[Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]]] = (
        Field(
            default=None,
            description="Filter scan results by severity level",
        )
    )
    state: Optional[
        List[
            Literal[
                "TO_VERIFY",
                "CONFIRMED",
                "URGENT",
                "NOT_EXPLOITABLE",
                "PROPOSED_NOT_EXPLOITABLE",
                "FALSE_POSITIVE",
            ]
        ]
    ] = Field(
        default=None,
        description="Filter scan results by state",
    )
    status: Optional[List[Literal["NEW", "RECURRENT", "FIXED"]]] = Field(
        default=None,
        description="Filter scan results by status",
    )
    exclude_result_types: Optional[List[Literal["DEV_AND_TEST", "NONE"]]] = Field(
        default=["DEV_AND_TEST"],
        description="Filter scan results by exclude result types",
    )


class CheckmarxOneScanResultResourcesConfig(ResourceConfig):
    kind: Literal["scan_result"]
    selector: CheckmarxOneResultSelector


class CheckmarxOneScanSelector(Selector):
    project_ids: List[str] = Field(
        default_factory=list,
        alias="projectIds",
        description="Limit search to specific project IDs",
    )


class CheckmarxOneScanResourcesConfig(ResourceConfig):
    kind: Literal["scan"]
    selector: CheckmarxOneScanSelector


class CheckmarxOnePortAppConfig(PortAppConfig):
    resources: List[
        CheckmarxOneScanResultResourcesConfig
        | CheckmarxOneScanResourcesConfig
        | ResourceConfig
    ] = Field(default_factory=list)


class CheckmarxOneIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = CheckmarxOnePortAppConfig
