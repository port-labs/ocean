from typing import Literal, Optional, List
from pydantic import BaseModel

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from pydantic import Field

from checkmarx_one.utils import days_ago_to_rfc3339


class CheckmarxOneScanModel(BaseModel):
    project_names: List[str] = Field(
        default_factory=list,
        alias="projectIds",
        title="Project Names",
        description="Filter scans by their project name",
    )
    branches: Optional[List[str]] = Field(
        default=None,
        title="Branches",
        description="Filter results by the name of the Git branch that was scanned.",
    )
    statuses: Optional[
        List[Literal["Queued", "Running", "Completed", "Failed", "Partial", "Canceled"]]
    ] = Field(
        default=None,
        title="Statuses",
        description="Filter results by the execution status of the scans. (Case insensitive, OR operator for multiple statuses.)",
    )
    since: Optional[int] = Field(
        ge=1,
        le=90,
        default=90,
        title="Since (Days)",
        description="Filter results to scans created within the last N days (1–90).",
    )

    @property
    def from_date(self) -> Optional[str]:
        return days_ago_to_rfc3339(self.since) if self.since else None


class CheckmarxOneResultSelector(Selector):
    scan_filter: CheckmarxOneScanModel = Field(
        default=CheckmarxOneScanModel(),
        title="Scan Filter",
        description="Filter scan results by scan",
    )
    severity: Optional[List[Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]]] = (
        Field(
            default=None,
            title="Severity",
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
        title="State",
        description="Filter scan results by state",
    )
    status: Optional[List[Literal["NEW", "RECURRENT", "FIXED"]]] = Field(
        default=None,
        title="Status",
        description="Filter scan results by status",
    )
    exclude_result_types: Optional[Literal["DEV_AND_TEST", "NONE"]] = Field(
        default="NONE",
        title="Exclude Result Types",
        description="Filter scan results by exclude result types",
    )


class CheckmarxOneSastSelector(Selector):
    scan_filter: CheckmarxOneScanModel = Field(
        default=CheckmarxOneScanModel(),
        title="Scan Filter",
        description="Filter scan results by scan",
    )
    compliance: Optional[str] = Field(
        default=None,
        title="Compliance",
        description="Filter by compliance standard (exact match, case insensitive).",
    )
    group: Optional[str] = Field(
        default=None,
        title="Group",
        description="Filter by vulnerability group (substring match).",
    )
    include_nodes: bool = Field(
        default=True,
        title="Include Nodes",
        description="If true, include nodes data; if false, omit node data.",
    )
    language: Optional[List[str]] = Field(
        default=None,
        title="Language",
        description="Filter by language (exact match, case insensitive).",
    )
    result_id: Optional[str] = Field(
        default=None,
        title="Result ID",
        description="Filter by unique result hash.",
    )
    severity: Optional[List[Literal["critical", "high", "medium", "low", "info"]]] = (
        Field(
            default=None,
            title="Severity",
            description="Filter by severity.",
        )
    )
    status: Optional[List[Literal["new", "recurrent", "fixed"]]] = Field(
        default=None,
        title="Status",
        description="Filter by status.",
    )
    category: Optional[str] = Field(
        default=None,
        title="Category",
        description="Filter by comma separated list of categories. (e.g. 'SQL_Injection,XSS')",
    )
    state: Optional[
        List[
            Literal[
                "to_verify",
                "not_exploitable",
                "proposed_not_exploitable",
                "confirmed",
                "urgent",
            ]
        ]
    ] = Field(
        default=None,
        title="State",
        description="Filter by state.",
    )


class CheckmarxOneApiSecSelector(Selector):
    scan_filter: CheckmarxOneScanModel = Field(
        default=CheckmarxOneScanModel(),
        title="Scan Filter",
        description="Filter scan results by scan",
    )


class CheckmarxOneApiSecResourcesConfig(ResourceConfig):
    kind: Literal["api-security"] = Field(
        title="Checkmarx API Security Result",
        description="An API security vulnerability result from a Checkmarx One scan",
    )
    selector: CheckmarxOneApiSecSelector = Field(
        title="API Security Selector",
        description="Selector for filtering API security vulnerability results",
    )


class CheckmarxOneScanSelector(Selector, CheckmarxOneScanModel): ...


class CheckmarxOneScanResourcesConfig(ResourceConfig):
    kind: Literal["scan"] = Field(
        title="Checkmarx Scan",
        description="A scan executed in Checkmarx One",
    )
    selector: CheckmarxOneScanSelector = Field(
        title="Scan Selector",
        description="Selector for filtering scans",
    )


class CheckmarxOneSastResourcesConfig(ResourceConfig):
    kind: Literal["sast"] = Field(
        title="Checkmarx SAST Result",
        description="A static application security testing (SAST) vulnerability result from a Checkmarx One scan",
    )
    selector: CheckmarxOneSastSelector = Field(
        title="SAST Selector",
        description="Selector for filtering SAST vulnerability results",
    )


class CheckmarxOneKicsSelector(Selector):
    scan_filter: CheckmarxOneScanModel = Field(
        default=CheckmarxOneScanModel(),
        title="Scan Filter",
        description="Filter scan results by scan",
    )
    severity: Optional[List[Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]]] = (
        Field(
            default=None,
            title="Severities",
            description="Filter KICS results by severity levels",
        )
    )
    status: Optional[List[Literal["NEW", "RECURRENT", "FIXED"]]] = Field(
        default=None,
        title="Statuses",
        description="Filter KICS results by status",
    )


class CheckmarxOneKicsResourcesConfig(ResourceConfig):
    kind: Literal["kics"] = Field(
        title="Checkmarx KICS Result",
        description="A KICS (Keeping Infrastructure as Code Secure) vulnerability result from a Checkmarx One scan",
    )
    selector: CheckmarxOneKicsSelector = Field(
        title="KICS Selector",
        description="Selector for filtering KICS vulnerability results",
    )


class CheckmarxOneScaResourcesConfig(ResourceConfig):
    kind: Literal["sca"] = Field(
        title="Checkmarx SCA Result",
        description="A software composition analysis (SCA) vulnerability result from a Checkmarx One scan",
    )
    selector: CheckmarxOneResultSelector = Field(
        title="SCA Selector",
        description="Selector for filtering SCA vulnerability results",
    )


class CheckmarxOneContainersResourcesConfig(ResourceConfig):
    kind: Literal["containers"] = Field(
        title="Checkmarx Container Security Result",
        description="A container security vulnerability result from a Checkmarx One scan",
    )
    selector: CheckmarxOneResultSelector = Field(
        title="Container Security Selector",
        description="Selector for filtering container security vulnerability results",
    )




class CheckmarxOneDastScanModel(BaseModel):
    scan_type: Optional[Literal["DAST", "DASTAPI"]] = Field(
        alias="scanType",
        default=None,
        title="Scan Type",
        description="Filter DAST scans by scan type",
    )
    since: Optional[int] = Field(
        ge=1,
        default=90,
        title="Since (Days)",
        description="Filter results by number of days when they were last updated. (1-90 days)",
    )
    max_results: int = Field(
        alias="maxResults",
        ge=1,
        le=3000,
        default=3000,
        title="Max Results",
        description="Limit the number of DAST scans returned",
    )

    @property
    def updated_from_date(self) -> str:
        """
        Returns the RFC 3339 date string for filtering by 'updated from' date, based on 'since' value.
        If 'since' is not provided, defaults to 90 days ago.
        """
        days = self.since if self.since is not None else 90
        return days_ago_to_rfc3339(days)


class CheckmarxOneDastScanSelector(Selector, CheckmarxOneDastScanModel): ...


class CheckmarxOneDastScanResourcesConfig(ResourceConfig):
    kind: Literal["dast-scan"] = Field(
        title="Checkmarx DAST Scan",
        description="A dynamic application security testing (DAST) scan from Checkmarx One",
    )
    selector: CheckmarxOneDastScanSelector = Field(
        title="DAST Scan Selector",
        description="Selector for filtering DAST scans",
    )


class CheckmarxOneDastScanResultFilter(BaseModel):
    severity: Optional[List[Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]]] = (
        Field(
            default=None,
            title="Severity",
            description="Filter DAST scan results by severity",
        )
    )
    status: Optional[List[Literal["NEW", "RECURRENT"]]] = Field(
        default=None,
        title="Status",
        description="Filter DAST scan results by status",
    )
    state: Optional[
        List[
            Literal[
                "TO_VERIFY",
                "NOT_EXPLOITABLE",
                "PROPOSED_NOT_EXPLOITABLE",
                "CONFIRMED",
                "URGENT",
            ]
        ]
    ] = Field(
        default=None,
        title="State",
        description="Filter DAST scan results by state",
    )


class CheckmarxOneDastScanResultSelector(Selector):
    dast_scan_filter: CheckmarxOneDastScanModel = Field(
        default=CheckmarxOneDastScanModel(),
        title="DAST Scan Filter",
        description="Filter scan results by DAST scan",
    )
    filter: CheckmarxOneDastScanResultFilter = Field(
        default=CheckmarxOneDastScanResultFilter(),
        title="Filter",
        description="Filter DAST scan results",
    )


class CheckmarxOneDastScanResultResourcesConfig(ResourceConfig):
    kind: Literal["dast-scan-result"] = Field(
        title="Checkmarx DAST Scan Result",
        description="A dynamic application security testing (DAST) vulnerability result from a Checkmarx One scan",
    )
    selector: CheckmarxOneDastScanResultSelector = Field(
        title="DAST Scan Result Selector",
        description="Selector for filtering DAST scan results",
    )


class CheckmarxOneApplicationSelector(Selector):
    """Selector for filtering applications."""

    tag_keys: Optional[List[str]] = Field(
        default=None,
        alias="tagKeys",
        title="Tag Keys",
        description="Filter applications by tag keys (e.g. ['env', 'team'])",
    )
    tag_values: Optional[List[str]] = Field(
        default=None,
        alias="tagValues",
        title="Tag Values",
        description="Filter applications by tag values (e.g. ['production', 'backend'])",
    )


class CheckmarxOneApplicationResourcesConfig(ResourceConfig):
    kind: Literal["application"] = Field(
        title="Checkmarx Application",
        description="An application defined in Checkmarx One",
    )
    selector: CheckmarxOneApplicationSelector = Field(
        title="Application Selector",
        description="Selector for filtering applications",
    )


class CheckmarxOneProjectResourcesConfig(ResourceConfig):
    kind: Literal["project"] = Field(
        title="Checkmarx Project",
        description="A project defined in Checkmarx One",
    )


class CheckmarxOnePortAppConfig(PortAppConfig):
    resources: list[
        CheckmarxOneScanResourcesConfig
        | CheckmarxOneApiSecResourcesConfig
        | CheckmarxOneSastResourcesConfig
        | CheckmarxOneKicsResourcesConfig
        | CheckmarxOneScaResourcesConfig
        | CheckmarxOneContainersResourcesConfig
        | CheckmarxOneDastScanResourcesConfig
        | CheckmarxOneDastScanResultResourcesConfig
        | CheckmarxOneApplicationResourcesConfig
        | CheckmarxOneProjectResourcesConfig
    ] = Field(default_factory=list)  # type: ignore[assignment]


class CheckmarxOneIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = CheckmarxOnePortAppConfig
