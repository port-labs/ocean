"""
Harbor API Response Schemas

These represent the actual data structures returned by Harbor's API
"""

from typing import TypedDict, Optional, Any
from typing_extensions import NotRequired

class ProjectMetadata(TypedDict, total=False):
    """Project metadata configuration"""
    public: str  # "true" or "false" as string
    enable_content_trust: str
    enable_content_trust_cosign: str
    prevent_vul: str
    severity: str
    auto_scan: str
    auto_sbom_generation: str
    reuse_sys_cve_allowlist: str
    retention_id: str


class CVEAllowlistItem(TypedDict):
    """Individual CVE in allowlist"""
    cve_id: str


class CVEAllowlist(TypedDict):
    """CVE allowlist for project"""
    id: int
    project_id: int
    items: list[CVEAllowlistItem]
    creation_time: str
    update_time: str
    expires_at: NotRequired[str]


class Project(TypedDict):
    """Harbor project"""
    project_id: int
    name: str
    owner_id: int
    owner_name: str
    repo_count: int
    creation_time: str
    update_time: str
    deleted: bool
    metadata: ProjectMetadata
    cve_allowlist: CVEAllowlist
    registry_id: NotRequired[int]
    togglable: NotRequired[bool]
    current_user_role_id: NotRequired[int]
    current_user_role_ids: NotRequired[list[int]]


class Repository(TypedDict):
    """Harbor repository"""
    id: int
    project_id: int
    name: str  # Full path: "project_name/repo_name"
    description: NotRequired[str]
    artifact_count: int
    pull_count: int
    creation_time: str
    update_time: str


class Tag(TypedDict):
    """Artifact tag"""
    id: int
    repository_id: int
    artifact_id: int
    name: str
    push_time: str
    pull_time: str
    immutable: bool


class Platform(TypedDict):
    """Platform information for multi-arch images"""
    architecture: str
    os: str
    os_version: NotRequired[str]
    os_features: NotRequired[list[str]]
    variant: NotRequired[str]


class Reference(TypedDict):
    """Artifact reference (for multi-arch images)"""
    parent_id: int
    child_id: int
    child_digest: str
    platform: NotRequired[Platform]
    annotations: NotRequired[dict[str, str]]
    urls: NotRequired[list[str]]


class VulnerabilitySummary(TypedDict):
    """Vulnerability count by severity"""
    total: int
    fixable: int
    summary: dict[str, int]  # {"Critical": 2, "High": 5, ...}


class NativeReportSummary(TypedDict):
    """Native vulnerability scan report summary"""
    report_id: str
    scan_status: str
    severity: str
    duration: int
    summary: VulnerabilitySummary
    start_time: str
    end_time: str
    scanner: NotRequired[dict[str, Any]]


class ScanOverview(TypedDict):
    """Scan overview - maps scanner name to report"""
    # Key is scanner name (e.g., "Trivy")
    # Value is NativeReportSummary
    pass  # This is a flexible dict


class Scanner(TypedDict):
    """SBOM scanner information"""
    name: str
    vendor: str
    version: str


class SBOMOverview(TypedDict):
    """SBOM generation overview"""
    start_time: str
    end_time: str
    scan_status: str
    sbom_digest: str
    report_id: str
    duration: int
    scanner: Scanner


class Accessory(TypedDict):
    """Artifact accessory (signature, SBOM, etc.)"""
    id: int
    artifact_id: int
    subject_artifact_id: int
    subject_artifact_digest: str
    subject_artifact_repo: str
    size: int
    digest: str
    type: str
    icon: str
    creation_time: str


class Label(TypedDict):
    """Artifact label"""
    id: int
    name: str
    description: NotRequired[str]
    color: str
    scope: str
    project_id: NotRequired[int]
    creation_time: str
    update_time: str


class Artifact(TypedDict):
    """Harbor artifact (container image, chart, etc.)"""
    id: int
    type: str  # "IMAGE", "CHART", etc.
    media_type: str
    manifest_media_type: str
    project_id: int
    repository_id: int
    digest: str
    size: int
    push_time: str
    pull_time: str
    icon: NotRequired[str]
    extra_attrs: NotRequired[dict[str, Any]]
    annotations: NotRequired[dict[str, str]]
    references: NotRequired[list[Reference]]
    tags: NotRequired[list[Tag]]
    labels: NotRequired[list[Label]]
    scan_overview: NotRequired[dict[str, NativeReportSummary]]  # Scanner name -> summary
    sbom_overview: NotRequired[SBOMOverview]
    accessories: NotRequired[list[Accessory]]
    addition_links: NotRequired[dict[str, Any]]

class WebhookTargetObject(TypedDict):
    """Webhook target configuration"""
    type: str  # "http", "slack", etc.
    address: str
    auth_header: NotRequired[str]
    skip_cert_verify: bool
    payload_format: str  # "Default", "CloudEvents"


class WebhookPolicy(TypedDict):
    """Webhook policy configuration"""
    id: int
    name: str
    description: NotRequired[str]
    project_id: int
    targets: list[WebhookTargetObject]
    event_types: list[str]  # ["PUSH_ARTIFACT", "DELETE_ARTIFACT", ...]
    creator: str
    creation_time: str
    update_time: str
    enabled: bool

class OIDCUserInfo(TypedDict):
    """OIDC user information"""
    id: int
    user_id: int
    subiss: str  # Concatenation of sub and issuer in ID token
    secret: str
    creation_time: str
    update_time: str

class UserResp(TypedDict):
    """Harbor user response"""
    user_id: int
    username: str
    email: str
    realname: str
    comment: str
    sysadmin_flag: bool
    admin_role_in_auth: bool  # Admin privilege granted by authenticator (LDAP)
    creation_time: str
    update_time: str
    oidc_user_meta: NotRequired[OIDCUserInfo]

class UserCreationReq(TypedDict):
    """User creation request payload"""
    username: str  # max 255 chars
    email: str  # max 255 chars
    realname: str
    password: str
    comment: NotRequired[str]


User = UserResp
"""Alias for Harbor user"""
