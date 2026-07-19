from typing import Any, Literal

from pydantic import BaseModel
from wiz.constants import VULNERABILITY_FINDING_SEVERITIES


class ParallelismConfig(BaseModel):
    strategy: Literal["auto", "date", "severity"]
    date_interval_days: int
    lookback_days: int
    api_requests_per_second: int
    max_partition_entities: int


class IssueOptions(BaseModel):
    max_pages: int
    status_list: list[Literal["OPEN", "IN_PROGRESS", "RESOLVED", "REJECTED"]]
    severity_list: (
        list[Literal["LOW", "MEDIUM", "HIGH", "CRITICAL", "INFORMATIONAL"]] | None
    ) = None
    type_list: (
        list[Literal["TOXIC_COMBINATION", "THREAT_DETECTION", "CLOUD_CONFIGURATION"]]
        | None
    ) = None


class ProjectOptions(BaseModel):
    include_archived: bool | None = None
    impact: Literal["LBI", "MBI", "HBI"] | None = None


class VulnerabilityFindingOptions(BaseModel):
    max_pages: int
    status_list: list[Literal["OPEN", "IN_PROGRESS", "RESOLVED", "REJECTED"]] | None = (
        None
    )
    severity_list: list[VULNERABILITY_FINDING_SEVERITIES] | None = (
        None
    )
    parallelism: ParallelismConfig | None = None


class SbomArtifactOptions(BaseModel):
    max_pages: int
    group_list: (
        list[
            Literal[
                "CODE_LIBRARY",
                "OS_PACKAGE",
                "PLUGIN",
                "CUSTOM",
                "CI_COMPONENT",
            ]
        ]
        | None
    ) = None
    resource_filter: dict[str, Any] | None = None
