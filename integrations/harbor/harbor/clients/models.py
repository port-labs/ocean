from typing import Any, Optional
from pydantic import BaseModel, Field


class ProjectMetadata(BaseModel):
    """Harbor project metadata."""

    public: Optional[str] = None

    class Config:
        extra = "allow"


class Project(BaseModel):
    """Harbor project."""

    project_id: int
    name: str
    owner_name: Optional[str] = None
    repo_count: Optional[int] = None
    creation_time: Optional[str] = None
    update_time: Optional[str] = None
    metadata: Optional[ProjectMetadata] = None

    class Config:
        extra = "allow"


class User(BaseModel):
    """Harbor user."""

    user_id: int
    username: str
    email: Optional[str] = None
    realname: Optional[str] = None
    has_admin_role: Optional[bool] = Field(default=None, alias="admin_role_in_auth")
    creation_time: Optional[str] = None
    update_time: Optional[str] = None

    class Config:
        extra = "allow"
        populate_by_name = True


class Repository(BaseModel):
    """Harbor repository."""

    name: str
    artifact_count: Optional[int] = None
    pull_count: Optional[int] = None
    creation_time: Optional[str] = None
    update_time: Optional[str] = None
    description: Optional[str] = None

    class Config:
        extra = "allow"


class Tag(BaseModel):
    """Harbor artifact tag."""

    name: str
    push_time: Optional[str] = None
    pull_time: Optional[str] = None

    class Config:
        extra = "allow"


class Label(BaseModel):
    """Harbor label."""

    name: str
    id: Optional[int] = None
    description: Optional[str] = None

    class Config:
        extra = "allow"


class VulnerabilitySummary(BaseModel):
    """Vulnerability count summary."""

    Critical: int = 0
    High: int = 0
    Medium: int = 0
    Low: int = 0
    Negligible: int = 0

    class Config:
        extra = "allow"


class ScanSummary(BaseModel):
    """Scan summary container."""

    summary: Optional[VulnerabilitySummary] = None

    class Config:
        extra = "allow"


class ScanOverviewItem(BaseModel):
    """Individual scan result."""

    scan_status: Optional[str] = None
    severity: Optional[str] = None
    summary: Optional[ScanSummary] = None

    class Config:
        extra = "allow"


class Artifact(BaseModel):
    """Harbor artifact."""

    digest: str
    size: Optional[int] = None
    push_time: Optional[str] = None
    pull_time: Optional[str] = None
    media_type: Optional[str] = None
    tags: Optional[list[Tag]] = None
    labels: Optional[list[Label]] = None
    scan_overview: Optional[dict[str, ScanOverviewItem]] = None

    class Config:
        extra = "allow"


class ArtifactFilter(BaseModel):
    """Filter configuration for artifacts."""

    min_severity: Optional[str] = None
    tag: Optional[str] = None
    digest: Optional[str] = None
    label: Optional[str] = None
    media_type: Optional[str] = None
    created_since: Optional[str] = None


class ProjectFilter(BaseModel):
    """Filter configuration for projects."""

    visibility: Optional[str] = None
    name_prefix: Optional[str] = None


class RepositoryFilter(BaseModel):
    """Filter configuration for repositories."""

    name_contains: Optional[str] = None
    name_starts_with: Optional[str] = None
