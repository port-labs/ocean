"""Mapping helpers for Harbor artifacts."""

from __future__ import annotations

from integrations.harbor.models import HarborArtifact, PortArtifactEntity


def map_artifact(artifact: HarborArtifact) -> PortArtifactEntity:
    project_name = artifact.get("project_name")
    repository = artifact.get("repository") or artifact.get("repository_name")
    repository_path = artifact.get("repository_path")
    digest = artifact.get("digest")

    if not isinstance(project_name, str) or not project_name:
        raise ValueError("artifact project_name is required")
    if not isinstance(repository_path, str) or not repository_path:
        raise ValueError("artifact repository_path is required")
    if not isinstance(repository, str) or not repository:
        repository = repository_path.split("/", 1)[-1]
    if not isinstance(digest, str) or not digest:
        raise ValueError("artifact digest is required")

    labels = artifact.get("labels") or []
    if not isinstance(labels, list):
        labels = []
    labels = [str(label) for label in labels if label is not None]

    return PortArtifactEntity(
        project_name=project_name,
        repository=repository,
        repository_path=repository_path,
        digest=digest,
        artifact_type=_coerce_optional_str(
            artifact.get("artifact_type") or artifact.get("type")
        ),
        media_type=_coerce_optional_str(artifact.get("media_type")),
        tag_count=int(artifact.get("tag_count") or 0),
        primary_tag=_coerce_optional_str(artifact.get("primary_tag")),
        labels=labels,
        created_at=_coerce_optional_str(artifact.get("created_at")),
        pushed_at=_coerce_optional_str(artifact.get("pushed_at")),
        vulnerability_severity=_coerce_optional_str(
            artifact.get("vulnerability_severity")
        )
        or "None",
        critical_vulnerability_count=int(
            artifact.get("critical_vulnerability_count") or 0
        ),
        high_vulnerability_count=int(artifact.get("high_vulnerability_count") or 0),
        medium_vulnerability_count=int(artifact.get("medium_vulnerability_count") or 0),
        low_vulnerability_count=int(artifact.get("low_vulnerability_count") or 0),
        negligible_vulnerability_count=int(
            artifact.get("negligible_vulnerability_count") or 0
        ),
        scan_completed_at=_coerce_optional_str(artifact.get("scan_completed_at")),
    )


def _coerce_optional_str(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)
