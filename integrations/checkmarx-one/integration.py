from typing import ClassVar, Literal, Optional, List
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
        description="Filter scans by their project name",
    )
    branches: Optional[List[str]] = Field(
        default=None,
        description="Filter results by the name of the Git branch that was scanned.",
    )
    statuses: Optional[
        List[Literal["Queued", "Running", "Completed", "Failed", "Partial", "Canceled"]]
    ] = Field(
        default=None,
        description="Filter results by the execution status of the scans. (Case insensitive, OR operator for multiple statuses.)",
    )
    since: Optional[int] = Field(
        ge=1,
        le=90,
        default=90,
        description="Filter results by the date and time when the scan was created. (UNIX timestamp in seconds)",
    )

    @property
    def from_date(self) -> Optional[str]:
        return days_ago_to_rfc3339(self.since) if self.since else None


class CheckmarxOneResultSelector(Selector):
    scan_filter: CheckmarxOneScanModel = Field(
        default=CheckmarxOneScanModel(),
        description="Filter scan results by scan",
    )
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
    exclude_result_types: Optional[Literal["DEV_AND_TEST", "NONE"]] = Field(
        default="NONE",
        description="Filter scan results by exclude result types",
    )


class CheckmarxOneSastSelector(Selector):
    scan_filter: CheckmarxOneScanModel = Field(
        default=CheckmarxOneScanModel(),
        description="Filter scan results by scan",
    )
    compliance: Optional[str] = Field(
        default=None,
        description="Filter by compliance standard (exact match, case insensitive).",
    )
    group: Optional[str] = Field(
        default=None,
        description="Filter by vulnerability group (substring match).",
    )
    include_nodes: bool = Field(
        default=True,
        description="If true, include nodes data; if false, omit node data.",
    )
    language: Optional[List[str]] = Field(
        default=None,
        description="Filter by language (exact match, case insensitive).",
    )
    result_id: Optional[str] = Field(
        default=None,
        description="Filter by unique result hash.",
    )
    severity: Optional[List[Literal["critical", "high", "medium", "low", "info"]]] = (
        Field(
            default=None,
            description="Filter by severity.",
        )
    )
    status: Optional[List[Literal["new", "recurrent", "fixed"]]] = Field(
        default=None,
        description="Filter by status.",
    )
    category: Optional[str] = Field(
        default=None,
        description="Filter by comma separated list of categories.",
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
        description="Filter by state.",
    )


class CheckmarxOneApiSecSelector(Selector):
    scan_filter: CheckmarxOneScanModel = Field(
        default=CheckmarxOneScanModel(),
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
        description="Filter scan results by scan",
    )
    severity: Optional[List[Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]]] = (
        Field(
            default=None,
            description="Filter KICS results by severity levels",
        )
    )
    status: Optional[List[Literal["NEW", "RECURRENT", "FIXED"]]] = Field(
        default=None,
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


class CheckmarxOneDastScanResultLegacyResourcesConfig(ResourceConfig):
    kind: Literal["dast_scan_result"] = Field(
        title="Checkmarx DAST Scan Result (Legacy)",
        description="A dynamic application security testing (DAST) vulnerability result from a Checkmarx One scan (legacy kind)",
    )
    selector: CheckmarxOneResultSelector = Field(
        title="DAST Scan Result Selector",
        description="Selector for filtering DAST scan results",
    )


class CheckmarxOneDastScanModel(BaseModel):
    scan_type: Optional[Literal["DAST", "DASTAPI"]] = Field(
        alias="scanType",
        default=None,
        description="Filter DAST scans by scan type",
    )
    since: Optional[int] = Field(
        ge=1,
        default=90,
        description="Filter results by number of days when they were last updated. (1-90 days)",
    )
    max_results: int = Field(
        alias="maxResults",
        ge=1,
        le=3000,
        default=3000,
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
            description="Filter DAST scan results by severity",
        )
    )
    status: Optional[List[Literal["NEW", "RECURRENT"]]] = Field(
        default=None,
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
        description="Filter DAST scan results by state",
    )


class CheckmarxOneDastScanResultSelector(Selector):
    dast_scan_filter: CheckmarxOneDastScanModel = Field(
        default=CheckmarxOneDastScanModel(),
        description="Filter scan results by DAST scan",
    )
    filter: CheckmarxOneDastScanResultFilter = Field(
        default=CheckmarxOneDastScanResultFilter(),
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
        description="Filter applications by tag keys",
    )
    tag_values: Optional[List[str]] = Field(
        default=None,
        alias="tagValues",
        description="Filter applications by tag values",
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


class CustomResourceConfig(ResourceConfig):
    kind: str = Field(title="Custom CheckmarxOne kinds", description="")


class CheckmarxOnePortAppConfig(PortAppConfig):
    resources: list[
        CheckmarxOneScanResourcesConfig
        | CheckmarxOneApiSecResourcesConfig
        | CheckmarxOneSastResourcesConfig
        | CheckmarxOneKicsResourcesConfig
        | CheckmarxOneScaResourcesConfig
        | CheckmarxOneContainersResourcesConfig
        | CheckmarxOneDastScanResultLegacyResourcesConfig
        | CheckmarxOneDastScanResourcesConfig
        | CheckmarxOneDastScanResultResourcesConfig
        | CheckmarxOneApplicationResourcesConfig
        | CustomResourceConfig
    ] = Field(default_factory=list)
    allow_custom_kinds: ClassVar[bool] = True


class CheckmarxOneIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = CheckmarxOnePortAppConfig
