"""Typed representations of Port entities emitted by the Harbor integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class PortEntity:
    """Base entity with helper for conversion to raw dictionaries."""

    def as_dict(self) -> dict[str, Any]:  # pragma: no cover - implemented in subclasses
        raise NotImplementedError


@dataclass(slots=True)
class PortProjectEntity(PortEntity):
    project_name: str
    display_name: str
    public: bool
    visibility: str
    repository_count: int
    owner: str | None = None
    member_usernames: list[str] = field(default_factory=list)
    member_roles: list[dict[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "project_name": self.project_name,
            "display_name": self.display_name,
            "public": self.public,
            "visibility": self.visibility,
            "repository_count": self.repository_count,
            "owner": self.owner,
            "members": self.member_usernames,
            "member_roles": self.member_roles,
        }


@dataclass(slots=True)
class PortRepositoryEntity(PortEntity):
    project_name: str
    repository_name: str
    repository_path: str
    artifact_count: int
    pull_count: int
    creation_time: str | None
    update_time: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "project_name": self.project_name,
            "repository_name": self.repository_name,
            "repository_path": self.repository_path,
            "artifact_count": self.artifact_count,
            "pull_count": self.pull_count,
            "creation_time": self.creation_time,
            "update_time": self.update_time,
        }


@dataclass(slots=True)
class PortArtifactEntity(PortEntity):
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

    def as_dict(self) -> dict[str, Any]:
        return {
            "project_name": self.project_name,
            "repository": self.repository,
            "repository_path": self.repository_path,
            "digest": self.digest,
            "artifact_type": self.artifact_type,
            "media_type": self.media_type,
            "tag_count": self.tag_count,
            "primary_tag": self.primary_tag,
            "labels": self.labels,
            "created_at": self.created_at,
            "pushed_at": self.pushed_at,
            "vulnerability_severity": self.vulnerability_severity,
            "critical_vulnerability_count": self.critical_vulnerability_count,
            "high_vulnerability_count": self.high_vulnerability_count,
            "medium_vulnerability_count": self.medium_vulnerability_count,
            "low_vulnerability_count": self.low_vulnerability_count,
            "negligible_vulnerability_count": self.negligible_vulnerability_count,
            "scan_completed_at": self.scan_completed_at,
        }


@dataclass(slots=True)
class PortUserEntity(PortEntity):
    username: str
    display_name: str
    email: str | None
    creation_time: str | None
    update_time: str | None
    is_robot: bool
    is_admin: bool
    projects: list[str]
    project_roles: list[dict[str, str]]
    role_names: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "username": self.username,
            "display_name": self.display_name,
            "email": self.email,
            "creation_time": self.creation_time,
            "update_time": self.update_time,
            "is_robot": self.is_robot,
            "is_admin": self.is_admin,
            "projects": self.projects,
            "project_roles": self.project_roles,
            "role_names": self.role_names,
        }
