from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortAppConfig,
    Selector,
)
from pydantic import Field


class IssueSelector(Selector):
    status_list: list[str] = Field(
        alias="statusList",
        description="List of statuses to filter issues by",
        default=["OPEN", "IN_PROGRESS"],
    )
    severity_list: list[str] = Field(
        alias="severityList",
        description="List of severities to filter issues by. If empty, all severities are fetched. Valid values are: LOW, MEDIUM, HIGH, CRITICAL, INFORMATIONAL.",
        default=[],
    )
    type_list: list[str] = Field(
        alias="typeList",
        description="List of issue types to fetch. If empty, all issue types are fetched. Valid values are: TOXIC_COMBINATION, THREAT_DETECTION, CLOUD_CONFIGURATION.",
        default=[],
    )


class IssueResourceConfig(ResourceConfig):
    selector: IssueSelector


class WizPortAppConfig(PortAppConfig):
    resources: list[IssueResourceConfig | ResourceConfig] = Field(default_factory=list)
    max_pages: int = Field(
        alias="maxPages",
        description="Maximum number of pages to fetch. By default, 500 pages are fetched.",
        default=500,
    )
