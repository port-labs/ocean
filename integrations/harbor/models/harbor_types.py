"""Type definitions representing Harbor API payloads used by the integration."""

from __future__ import annotations

from typing import NotRequired, TypedDict


class HarborProjectMemberRole(TypedDict, total=False):
    username: str
    role: str


class HarborProject(TypedDict, total=False):
    project_id: int | None
    project_name: str
    display_name: str | None
    public: bool
    visibility: str
    repository_count: int
    owner: str | None
    members: list[str]
    member_roles: list[HarborProjectMemberRole]


class HarborRepository(TypedDict, total=False):
    repository_id: NotRequired[int | None]
    project_id: NotRequired[int | None]
    project_name: str
    repository_name: str
    repository_path: str
    artifact_count: int
    pull_count: int
    creation_time: str | None
    update_time: str | None


class HarborArtifactVulnerabilitySummary(TypedDict, total=False):
    highest_severity: str
    summary: dict[str, int]
    last_scan_time: str | None


class HarborArtifact(TypedDict, total=False):
    project_name: str
    repository: str
    repository_path: str
    digest: str
    artifact_type: str | None
    media_type: str | None
    tag_count: int
    primary_tag: str | None
    labels: list[str]
    created_at: str | None
    pushed_at: str | None
    vulnerability_severity: str
    critical_vulnerability_count: int
    high_vulnerability_count: int
    medium_vulnerability_count: int
    low_vulnerability_count: int
    negligible_vulnerability_count: int
    scan_completed_at: str | None


class HarborUserProjectRole(TypedDict, total=False):
    project: str
    role: str


class HarborUser(TypedDict, total=False):
    user_id: int | None
    username: str
    display_name: str
    email: str | None
    creation_time: str | None
    update_time: str | None
    is_robot: bool
    is_admin: bool
    projects: list[str]
    project_roles: list[HarborUserProjectRole]
    role_names: list[str]
