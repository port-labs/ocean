from typing import Any, Optional
from pydantic import BaseModel, Field

from snyk.overrides import SnykProjectAPIQueryParams, SnykVulnerabilityAPIQueryParams


class ProjectOptions(BaseModel):
    api_params: Optional[SnykProjectAPIQueryParams] = None
    org: dict[str, Any]
    enrich_with_org: bool = Field(default=True)


class IssueOptions(BaseModel):
    api_params: Optional[SnykVulnerabilityAPIQueryParams] = None
    project_params: Optional[SnykProjectAPIQueryParams] = None
    org: dict[str, Any]
    attach_project: bool = Field(default=False)
