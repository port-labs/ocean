from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortAppConfig,
    Selector,
)
from pydantic import Field
from typing import Literal


class IssueSelector(Selector):
    status_list: list[str] = Field(
        alias="statusList",
        description="List of statuses to filter issues by",
        default=["OPEN", "IN_PROGRESS"],
    )
    severity_list: list[
        Literal["LOW", "MEDIUM", "HIGH", "CRITICAL", "INFORMATIONAL"]
    ] = Field(
        alias="severityList",
        description="List of severities to filter issues by. If empty, all severities are fetched.",
        default=[],
    )
    type_list: list[
        Literal["TOXIC_COMBINATION", "THREAT_DETECTION", "CLOUD_CONFIGURATION"]
    ] = Field(
        alias="typeList",
        description="List of issue types to fetch. If empty, all issue types are fetched.",
        default=[],
    )


class IssueResourceConfig(ResourceConfig):
    selector: IssueSelector


class WizPortAppConfig(PortAppConfig):
    resources: list[IssueResourceConfig | ResourceConfig] = Field(default_factory=list)
