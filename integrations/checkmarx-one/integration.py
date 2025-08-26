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
    scanner_types: Optional[List[Literal["sast", "sca", "kics", "container-security", "api-security", "dast"]]] = Field(
        default=None,
        description="Filter results by scanner types (SAST, SCA, KICS, Container Security, API Security, DAST)",
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
    scanner_types: Optional[List[Literal["sast", "sca", "kics", "container-security", "api-security", "dast"]]] = Field(
        default=None,
        description="Filter scans by scanner types (SAST, SCA, KICS, Container Security, API Security, DAST)",
    )
    scan_status: Optional[List[Literal["Queued", "Running", "Completed", "Failed", "Canceled", "Partial"]]] = Field(
        default=None,
        description="Filter scans by status",
    )


class CheckmarxOneScanResourcesConfig(ResourceConfig):
    kind: Literal["scan"]
    selector: CheckmarxOneScanSelector


class CheckmarxOneApplicationSelector(Selector):
    criticality: Optional[List[Literal[1, 2, 3]]] = Field(
        default=None,
        description="Filter applications by criticality level (1=Low, 2=Medium, 3=High)",
    )


class CheckmarxOneApplicationResourcesConfig(ResourceConfig):
    kind: Literal["application"]
    selector: CheckmarxOneApplicationSelector


class CheckmarxOneProjectSelector(Selector):
    application_ids: List[str] = Field(
        default_factory=list,
        alias="applicationIds", 
        description="Limit search to specific application IDs",
    )
    groups: Optional[List[str]] = Field(
        default=None,
        description="Filter projects by groups",
    )


class CheckmarxOneProjectResourcesConfig(ResourceConfig):
    kind: Literal["project"]
    selector: CheckmarxOneProjectSelector


class CheckmarxOnePortAppConfig(PortAppConfig):
    resources: List[
        CheckmarxOneScanResultResourcesConfig
        | CheckmarxOneScanResourcesConfig
        | CheckmarxOneApplicationResourcesConfig
        | CheckmarxOneProjectResourcesConfig
        | ResourceConfig
    ] = Field(default_factory=list)


class CheckmarxOneIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = CheckmarxOnePortAppConfig
