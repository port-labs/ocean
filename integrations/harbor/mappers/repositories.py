"""Mapping helpers for Harbor repositories."""

from __future__ import annotations

from typing import Mapping

from integrations.harbor.models import HarborRepository, PortRepositoryEntity


def map_repository(repository: HarborRepository) -> PortRepositoryEntity:
    project_name = repository.get("project_name") or repository.get("project")
    if not isinstance(project_name, str) or not project_name:
        raise ValueError("repository project_name is required")

    repository_path = repository.get("repository_path") or repository.get("name")
    if not isinstance(repository_path, str) or not repository_path:
        raise ValueError("repository_path is required")

    repository_name = repository.get("repository_name")
    if not isinstance(repository_name, str) or not repository_name:
        repository_name = repository_path.split("/", 1)[-1]

    artifact_count = _coerce_int(repository.get("artifact_count"))
    pull_count = _coerce_int(repository.get("pull_count"))

    creation_time = _coerce_str(
        repository.get("creation_time") or repository.get("creationTime")
    )
    update_time = _coerce_str(
        repository.get("update_time") or repository.get("updateTime")
    )

    return PortRepositoryEntity(
        project_name=project_name,
        repository_name=repository_name,
        repository_path=repository_path,
        artifact_count=artifact_count,
        pull_count=pull_count,
        creation_time=creation_time,
        update_time=update_time,
    )


def _coerce_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _coerce_str(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)
