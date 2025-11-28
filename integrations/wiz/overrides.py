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
    kind: Literal["issue", "control", "serviceTicket"]


class ProjectSelector(Selector):
    impact: str = Field(
        alias="impact",
        description="The business impact of the project. If empty, all projects are fetched. Valid values are: LBI, MBI, HBI",
        default="",
    )
    include_archived: bool = Field(
        alias="includeArchived",
        description="Include archived projects. False by default.",
        default=False,
    )


class ProjectResourceConfig(ResourceConfig):
    selector: ProjectSelector
    kind: Literal["project"]


class WizPortAppConfig(PortAppConfig):
    resources: list[
        IssueResourceConfig
        | ProjectResourceConfig
        # | ControlResourceConfig
        # | ServiceTicketResourceConfig
        | ResourceConfig
    ] = Field(default_factory=list)
    issues_max_pages: int = Field(
        alias="issuesMaxPages",
        description="Maximum number of pages to fetch for issues. By default, 500 pages are fetched.",
        default=500,
    )
