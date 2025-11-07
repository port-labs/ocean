"""Pydantic models for the Harbor Integration entities"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from pydantic.fields import Field


class HarborProjectMetadata(BaseModel):
    """Metadata for Harbor project"""

    public: str = "false"
    enable_content_trust: Optional[str] = None
    prevent_vul: Optional[str] = None
    severity: Optional[str] = None
    auto_scan: Optional[str] = None
    auto_sbom_generation: Optional[str] = None


class HarborProject(BaseModel):
    """Harbor project model"""

    project_id: int
    name: str
    owner_id: Optional[int] = None
    owner_name: Optional[str] = None
    creation_time: Optional[datetime]
    update_time: Optional[datetime]
    deleted: bool = False
    repo_count: int = 0
    metadata: Optional[Dict[str, Any]] = None


class HarborUser(BaseModel):
    """Harbor user model"""

    user_id: int
    username: str
    email: Optional[str] = None
    realname: Optional[str] = None
    creation_time: Optional[datetime] = None
    update_time: Optional[datetime] = None
    sysadmin_flag: bool = False
    admin_role: bool = False


class HarborRepository(BaseModel):
    """Harbor repository model"""

    id: int
    project_id: int
    name: str
    description: Optional[str] = None
    artifact_count: Optional[int] = 0
    pull_count: int = 0
    creation_time: Optional[datetime] = None
    update_time: Optional[datetime] = None


class HarborPlatform(BaseModel):
    """Harbor platform model"""

    architecture: str
    os: str
    os_version: Optional[str] = Field(None, alias="'os.version'")
    os_features: Optional[List[str]] = Field(None, alias="'os.features'")
    variant: Optional[str] = None


class HarborReference(BaseModel):
    """Harbor artifact reference model"""

    parent_id: int
    child_id: int
    child_digest: str
    platform: Optional[HarborPlatform] = None
    annotations: Optional[Dict[str, str]] = None
    urls: Optional[List[str]] = None


class HarborTag(BaseModel):
    """Harbor artifact tag model"""

    id: int
    repository_id: int
    artifact_id: int
    name: str
    push_time: datetime
    pull_time: datetime
    immutable: bool


class HarborLabel(BaseModel):
    """Harbor label model"""

    id: int
    name: str
    description: Optional[str] = None
    color: Optional[str] = None
    scope: Optional[str] = None
    project_id: int
    creation_time: datetime
    update_time: datetime


class HarborVulnerabilitySummary(BaseModel):
    """Summary of vulnerabilities by severity"""

    Critical: Optional[int] = 0
    High: Optional[int] = 0


class HarborScanSummary(BaseModel):
    """Summary of a Harbor scan"""

    total: int
    fixable: int
    summary: HarborVulnerabilitySummary


class HarborScanner(BaseModel):
    """Harbor scanner model"""

    name: str
    vendor: str
    version: str


class HarborScanOverviewItem(BaseModel):
    """Overview of a Harbor scan for an artifact"""

    report_id: str
    scan_status: str
    severity: str
    duration: int
    summary: HarborScanSummary
    start_time: datetime
    end_time: datetime
    complete_percent: int
    scanner: HarborScanner


class HarborSBOMOverview(BaseModel):
    """Overview of a Harbor SBOM generation for an artifact"""

    start_time: datetime
    end_time: datetime
    scan_status: str
    sbom_digest: str
    report_id: str
    duration: int
    scanner: HarborScanner


class HarborAccessory(BaseModel):
    """Harbor accessory model"""

    id: int
    artifact_id: int
    subject_artifact_id: int
    subject_artifact_digest: str
    subject_artifact_repo: str
    size: int
    digest: str
    type: str
    icon: str
    creation_time: datetime


class HarborArtifact(BaseModel):
    """Harbor artifact model"""

    id: int
    type: str
    media_type: str
    manifest_media_type: str
    project_id: int
    repository_id: int
    digest: str
    size: int
    icon: Optional[str] = None
    push_time: datetime
    pull_time: datetime
    extra_attrs: Optional[Dict[str, Any]] = None
    annotations: Optional[Dict[str, str]] = None
    references: Optional[List[HarborReference]] = None
    tags: Optional[List[HarborTag]] = None
    addition_links: Optional[Dict[str, Dict[str, Any]]] = None
    labels: Optional[List[HarborLabel]] = None
    scan_overview: Optional[Dict[str, HarborScanOverviewItem]] = None
    sbom_overview: Optional[Dict[str, HarborSBOMOverview]] = None
    accessories: Optional[List[HarborAccessory]] = None

    @property
    def tag_names(self) -> List[str]:
        """Get list of tag names for the artifact"""

        tags = self.tags or []
        return [tag.name for tag in tags]

    @property
    def latest_tag(self) -> Optional[str]:
        """Get the latest tag based on push_time"""

        if not self.tags:
            return None
        return max(self.tags, key=lambda tag: tag.push_time).name

    @property
    def max_severity(self) -> str:
        """Get highest severity from all scanners"""

        if not self.scan_overview:
            return "None"

        severities = []
        for _, overview in self.scan_overview.items():
            if overview.scan_status == "Success" and overview.severity:
                severities.append(overview.severity)

        if not severities:
            return "None"

        severity_order = ["Critical", "High", "Medium", "Low", "None"]
        for severity in severity_order:
            if severity in severities:
                return severity

        return "None"

    @property
    def total_vulnerabilities(self) -> int:
        """Get total number of vulnerabilities from all scanners"""

        if not self.scan_overview:
            return 0

        total = 0
        for _, overview in self.scan_overview.items():
            if overview.scan_status == "Success" and overview.summary:
                total += overview.summary.total
        return total

    @property
    def scanner_names(self) -> List[str]:
        """Get list of scanner names that have scanned this artifact"""

        if not self.scan_overview:
            return []
        return list(self.scan_overview.keys())
