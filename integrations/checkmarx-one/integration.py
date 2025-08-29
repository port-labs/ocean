from typing import Literal, Optional, List, Union

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
        default=None,
        description="Filter scan results by exclude result types",
    )


class CheckmarxOneApiSecSelector(Selector):
    filtering: Optional[str] = Field(
        default=None,
        description="Filter API sec risks by fields",
    )
    searching: Optional[str] = Field(
        default=None,
        description="Full text search for API sec risks",
    )
    sorting: Optional[str] = Field(default=None, description="Sort API sec risks")


class CheckmarxOneProjectSelector(Selector):
    pass


class CheckmarxOneProjectResourcesConfig(ResourceConfig):
    kind: Literal["project"]
    selector: CheckmarxOneProjectSelector


class CheckmarxOneScaResourcesConfig(ResourceConfig):
    kind: Literal["sca"]
    selector: CheckmarxOneResultSelector


class CheckmarxOneKicsResourcesConfig(ResourceConfig):
    kind: Literal["kics"]
    selector: CheckmarxOneResultSelector


class CheckmarxOneContainersResourcesConfig(ResourceConfig):
    kind: Literal["containersec"]
    selector: CheckmarxOneResultSelector


class CheckmarxOneSastResourcesConfig(ResourceConfig):
    kind: Literal["sast"]
    selector: CheckmarxOneResultSelector


class CheckmarxOneApiSecResourcesConfig(ResourceConfig):
    kind: Literal["apisec"]
    selector: CheckmarxOneApiSecSelector


class CheckmarxOneScanSelector(Selector):
    project_ids: List[str] = Field(
        default_factory=list,
        alias="projectIds",
        description="Limit search to specific project IDs",
    )


class CheckmarxOneScanResourcesConfig(ResourceConfig):
    kind: Literal["scan"]
    selector: CheckmarxOneScanSelector


# Union type for all scan result configs
ScanResultConfigType = Union[
    CheckmarxOneScaResourcesConfig,
    CheckmarxOneKicsResourcesConfig,
    CheckmarxOneContainersResourcesConfig,
    CheckmarxOneSastResourcesConfig,
]


class CheckmarxOnePortAppConfig(PortAppConfig):
    resources: List[
        CheckmarxOneProjectResourcesConfig
        | CheckmarxOneScanResourcesConfig
        | ScanResultConfigType
        | CheckmarxOneApiSecResourcesConfig
    ] = Field(
        default_factory=list
    )  # type: ignore


class CheckmarxOneIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = CheckmarxOnePortAppConfig
