from typing import Any, Literal

from pydantic import BaseModel, Field


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
    status_list: list[Literal["OPEN", "IN_PROGRESS", "RESOLVED", "REJECTED"]] = Field(
        default=None,  # type: ignore[arg-type]
    )
    severity_list: list[Literal["LOW", "MEDIUM", "HIGH", "CRITICAL", "NONE"]] | None = (
        None
    )


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
