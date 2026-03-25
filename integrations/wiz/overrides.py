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
        title="Statuses",
        description="List of statuses to filter issues by",
        default=["OPEN", "IN_PROGRESS"],
    )
    severity_list: Optional[
        list[Literal["LOW", "MEDIUM", "HIGH", "CRITICAL", "INFORMATIONAL"]]
    ] = Field(
        alias="severityList",
        title="Severities",
        description="List of severities to filter issues by. If empty, all severities are fetched.",
        default=None,
    )
    type_list: Optional[
        list[Literal["TOXIC_COMBINATION", "THREAT_DETECTION", "CLOUD_CONFIGURATION"]]
    ] = Field(
        alias="typeList",
        title="Types",
        description="List of issue types to fetch. If empty, all issue types are fetched.",
        default=None,
    )
    max_pages: int = Field(
        alias="maxPages",
        title="Max Pages",
        description="Maximum number of pages to fetch for issues.",
        default=500,
    )


class IssueResourceConfig(ResourceConfig):
    selector: IssueSelector = Field(
        title="Issue Selector",
        description="Selector for the issue resource.",
    )
    kind: Literal["issue"] = Field(
        title="Wiz Issue",
        description="A security issue detected by Wiz.",
    )


class ControlResourceConfig(ResourceConfig):
    selector: IssueSelector = Field(
        title="Control Selector",
        description="Selector for the control resource.",
    )
    kind: Literal["control"] = Field(
        title="Wiz Control",
        description="A Wiz security control that triggered an issue.",
    )


class ServiceTicketResourceConfig(ResourceConfig):
    selector: IssueSelector = Field(
        title="Service Ticket Selector",
        description="Selector for the service ticket resource.",
    )
    kind: Literal["serviceTicket"] = Field(
        title="Wiz Service Ticket",
        description="A service ticket linked to a Wiz issue.",
    )


class ProjectSelector(Selector):
    impact: Optional[Literal["LBI", "MBI", "HBI"]] = Field(
        alias="impact",
        title="Impact",
        description="The business impact of the project. If empty, all projects are fetched.",
        default=None,
    )
    include_archived: Optional[bool] = Field(
        alias="includeArchived",
        title="Include Archived",
        description="Include archived projects. False by default.",
        default=None,
    )


class ProjectResourceConfig(ResourceConfig):
    selector: ProjectSelector = Field(
        title="Project Selector",
        description="Selector for the project resource.",
    )
    kind: Literal["project"] = Field(
        title="Wiz Project",
        description="A Wiz project grouping cloud resources and security findings.",
    )


class VulnerabilityFindingSelector(Selector):
    status_list: list[Literal["OPEN", "IN_PROGRESS", "RESOLVED", "REJECTED"]] = Field(
        alias="statusList",
        title="Statuses",
        description="List of statuses to filter vulnerability findings by",
        default=["OPEN", "IN_PROGRESS"],
    )
    severity_list: Optional[
        list[Literal["LOW", "MEDIUM", "HIGH", "CRITICAL", "NONE"]]
    ] = Field(
        alias="severityList",
        title="Severities",
        description="List of severities to filter vulnerability findings by. If empty, all severities are fetched.",
        default=None,
    )
    max_pages: int = Field(
        alias="maxPages",
        title="Max Pages",
        description="Maximum number of pages to fetch for vulnerability findings.",
        default=500,
    )


class VulnerabilityFindingResourceConfig(ResourceConfig):
    selector: VulnerabilityFindingSelector = Field(
        title="Vulnerability Finding Selector",
        description="Selector for the vulnerability finding resource.",
    )
    kind: Literal["vulnerability-finding"] = Field(
        title="Wiz Vulnerability Finding",
        description="A vulnerability finding detected by Wiz in a cloud resource.",
    )


class TechnologyResourceConfig(ResourceConfig):
    selector: Selector = Field(
        title="Technology Selector",
        description="Selector for the technology resource.",
    )
    kind: Literal["technology"] = Field(
        title="Wiz Technology",
        description="A software technology detected by Wiz across cloud resources.",
    )


class HostedTechnologyResourceConfig(ResourceConfig):
    selector: Selector = Field(
        title="Hosted Technology Selector",
        description="Selector for the hosted technology resource.",
    )
    kind: Literal["hosted-technology"] = Field(
        title="Wiz Hosted Technology",
        description="A hosted technology detected by Wiz in a cloud environment.",
    )


class RepositoryResourceConfig(ResourceConfig):
    selector: Selector = Field(
        title="Repository Selector",
        description="Selector for the repository resource.",
    )
    kind: Literal["repository"] = Field(
        title="Wiz Repository",
        description="A code repository tracked by Wiz.",
    )


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
        title="Groups",
        description="List of SBOM artifact groups to fetch. If empty, all groups are fetched.",
        default=["CODE_LIBRARY", "OS_PACKAGE", "PLUGIN", "CUSTOM", "CI_COMPONENT"],
    )
    max_pages: int = Field(
        alias="maxPages",
        title="Max Pages",
        description="Maximum number of pages to fetch for both grouped names and detailed SBOM artifacts.",
        default=500,
    )


class SbomArtifactResourceConfig(ResourceConfig):
    selector: SbomArtifactSelector = Field(
        title="SBOM Artifact Selector",
        description="Selector for the SBOM artifact resource.",
    )
    kind: Literal["sbom-artifact"] = Field(
        title="Wiz SBOM Artifact",
        description="A software bill of materials artifact tracked by Wiz.",
    )


class WizPortAppConfig(PortAppConfig):
    resources: list[
        IssueResourceConfig
        | ControlResourceConfig
        | ServiceTicketResourceConfig
        | ProjectResourceConfig
        | VulnerabilityFindingResourceConfig
        | TechnologyResourceConfig
        | HostedTechnologyResourceConfig
        | RepositoryResourceConfig
        | SbomArtifactResourceConfig
    ] = Field(default_factory=list)  # type: ignore[assignment]
