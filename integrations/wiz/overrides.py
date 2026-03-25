from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortAppConfig,
    Selector,
)
from pydantic import Field
from typing import Literal, Optional


class IssueSelector(Selector):
    status_list: list[Literal["OPEN", "IN_PROGRESS", "RESOLVED", "REJECTED"]] = Field(
        alias="statusList",
        description="List of statuses to filter issues by",
        default=["OPEN", "IN_PROGRESS"],
    )
    severity_list: Optional[
        list[Literal["LOW", "MEDIUM", "HIGH", "CRITICAL", "INFORMATIONAL"]]
    ] = Field(
        alias="severityList",
        description="List of severities to filter issues by. If empty, all severities are fetched.",
        default=None,
    )
    type_list: Optional[
        list[Literal["TOXIC_COMBINATION", "THREAT_DETECTION", "CLOUD_CONFIGURATION"]]
    ] = Field(
        alias="typeList",
        description="List of issue types to fetch. If empty, all issue types are fetched.",
        default=None,
    )
    max_pages: int = Field(
        alias="maxPages",
        description="Maximum number of pages to fetch for issues. By default, 500 pages are fetched.",
        default=500,
    )


class IssueResourceConfig(ResourceConfig):
    selector: IssueSelector
    kind: Literal["issue", "control", "serviceTicket"]


class ProjectSelector(Selector):
    impact: Optional[Literal["LBI", "MBI", "HBI"]] = Field(
        alias="impact",
        description="The business impact of the project. If empty, all projects are fetched.",
        default=None,
    )
    include_archived: Optional[bool] = Field(
        alias="includeArchived",
        description="Include archived projects. False by default.",
        default=None,
    )


class ProjectResourceConfig(ResourceConfig):
    selector: ProjectSelector
    kind: Literal["project"]


class VulnerabilityFindingSelector(Selector):
    status_list: list[Literal["OPEN", "IN_PROGRESS", "RESOLVED", "REJECTED"]] = Field(
        alias="statusList",
        description="List of statuses to filter vulnerability findings by",
        default=["OPEN", "IN_PROGRESS"],
    )
    severity_list: Optional[
        list[Literal["LOW", "MEDIUM", "HIGH", "CRITICAL", "NONE"]]
    ] = Field(
        alias="severityList",
        description="List of severities to filter vulnerability findings by. If empty, all severities are fetched.",
        default=None,
    )
    max_pages: int = Field(
        alias="maxPages",
        description="Maximum number of pages to fetch for vulnerability findings. By default, 500 pages are fetched.",
        default=500,
    )


class VulnerabilityFindingResourceConfig(ResourceConfig):
    selector: VulnerabilityFindingSelector
    kind: Literal["vulnerability-finding"]


class SbomArtifactSelector(Selector):
    group_list: Optional[
        list[
            Literal[
                "CODE_LIBRARY",
                "OS_PACKAGE",
                "PLUGIN",
                "CUSTOM",
                "CI_COMPONENT",
            ]
        ]
    ] = Field(
        alias="groupList",
        description="List of SBOM artifact groups to fetch. If empty, all groups are fetched.",
        default=["CODE_LIBRARY", "OS_PACKAGE", "PLUGIN", "CUSTOM", "CI_COMPONENT"],
    )
    max_pages: int = Field(
        alias="maxPages",
        description="Maximum number of pages to fetch for both grouped names and detailed SBOM artifacts. By default, 500 pages are fetched.",
        default=500,
    )


class SbomArtifactResourceConfig(ResourceConfig):
    selector: SbomArtifactSelector
    kind: Literal["sbom-artifact"]


class WizPortAppConfig(PortAppConfig):
    resources: list[
        IssueResourceConfig
        | ProjectResourceConfig
        | VulnerabilityFindingResourceConfig
        | SbomArtifactResourceConfig
        | ResourceConfig
    ] = Field(default_factory=list)
