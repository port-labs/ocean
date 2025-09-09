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

from datetime import datetime, timedelta, timezone


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
        min_value=1,
        default=90,
        description="Filter results by the date and time when the scan was created. (UNIX timestamp in seconds)",
    )

    @property
    def from_date(self) -> Optional[str]:
        return self._days_ago_to_rfc3339(self.since) if self.since else None

    def _days_ago_to_rfc3339(self, days: int) -> str:
        dt = datetime.now(timezone.utc) - timedelta(days=days)
        # Format to RFC3339 with microseconds and Zulu time
        # RFC3339 Date (Extend) format (e.g. 2021-06-02T12:14:18.028555Z)
        return dt.isoformat(timespec="microseconds").replace("+00:00", "Z")


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


class CheckmarxOneProjectSelector(Selector):
    pass


class CheckmarxOneProjectResourcesConfig(ResourceConfig):
    kind: Literal["project"]
    selector: CheckmarxOneProjectSelector


class CheckmarxOneApiSecResourcesConfig(ResourceConfig):
    kind: Literal["api-security"]
    selector: CheckmarxOneApiSecSelector


class CheckmarxOneScanSelector(Selector, CheckmarxOneScanModel): ...


class CheckmarxOneScanResourcesConfig(ResourceConfig):
    kind: Literal["scan"]
    selector: CheckmarxOneScanSelector


class CheckmarxOneSastResourcesConfig(ResourceConfig):
    kind: Literal["sast"]
    selector: CheckmarxOneSastSelector


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
    kind: Literal["kics"]
    selector: CheckmarxOneKicsSelector


class CheckmarxOneScanResultResourcesConfig(ResourceConfig):
    kind: Literal["sca", "containers"]
    selector: CheckmarxOneResultSelector


class CheckmarxOnePortAppConfig(PortAppConfig):
    resources: List[
        CheckmarxOneProjectResourcesConfig
        | CheckmarxOneScanResourcesConfig
        | CheckmarxOneApiSecResourcesConfig
        | CheckmarxOneSastResourcesConfig
        | CheckmarxOneKicsResourcesConfig
        | CheckmarxOneScanResultResourcesConfig
    ] = Field(
        default_factory=list
    )  # type: ignore


class CheckmarxOneIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = CheckmarxOnePortAppConfig
