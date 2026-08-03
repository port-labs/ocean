from typing import List, Literal, NotRequired, Optional, Required, TypedDict


class ListProjectOptions(TypedDict):
    org_uuid: Required[str]


class SingleProjectOptions(TypedDict):
    project_uuid: Required[str]


class ListScaVulnerabilityOptions(TypedDict):
    project_uuid: Required[str]
    project_name: NotRequired[str]
    severity: NotRequired[Optional[List[Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]]]]


class SingleScaVulnerabilityOptions(TypedDict):
    project_uuid: Required[str]
    finding_uuid: Required[str]
