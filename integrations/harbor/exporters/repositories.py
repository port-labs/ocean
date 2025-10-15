from __future__ import annotations

from typing import Any, AsyncGenerator, Iterable, Mapping

from loguru import logger
from urllib.parse import quote

from integrations.harbor.client import HarborClient


class RepositoriesExporter:
    """Stream Harbor repositories for selected projects with filtering support."""

    REPOSITORIES_PATH_TEMPLATE = "/projects/{project}/repositories"

    def __init__(
        self,
        client: HarborClient,
        project_records: Iterable[Mapping[str, Any]],
        *,
        project_filter: Iterable[str] | None = None,
        name_prefix: str | None = None,
        name_contains: str | None = None,
    ) -> None:
        self.client = client
        self.projects: list[tuple[str, int | None]] = []
        for record in project_records:
            project_name = record.get("project_name") or record.get("name")
            if not isinstance(project_name, str) or not project_name:
                continue
            project_id = record.get("project_id")
            try:
                project_id_int = int(project_id) if project_id is not None else None
            except (TypeError, ValueError):
                project_id_int = None
            self.projects.append((project_name, project_id_int))

        self.project_filter = (
            {name.strip().lower() for name in project_filter if name and name.strip()}
            if project_filter
            else None
        )
        self.name_prefix = name_prefix.strip().lower() if name_prefix else None
        self.name_contains = name_contains.strip().lower() if name_contains else None

    async def iter_repositories(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Yield repositories in pages applying configured filters."""

        for project_name, project_id in self._iter_projects():
            encoded_project = quote(project_name, safe="")
            path = self.REPOSITORIES_PATH_TEMPLATE.format(project=encoded_project)

            async for page in self.client.iter_pages(path):
                if not page:
                    continue

                transformed: list[dict[str, Any]] = []
                for item in page:
                    mapped = self._transform_repository(item, project_name, project_id)
                    if mapped is not None:
                        transformed.append(mapped)

                if transformed:
                    logger.debug(
                        "harbor.repositories.page_processed",
                        project=project_name,
                        count=len(transformed),
                        input_count=len(page),
                    )
                    yield transformed

    def _iter_projects(self) -> Iterable[tuple[str, int | None]]:
        if not self.project_filter:
            return self.projects
        return [
            (project_name, project_id)
            for project_name, project_id in self.projects
            if project_name.lower() in self.project_filter
        ]

    def _transform_repository(
        self,
        repository: Any,
        project_name: str,
        project_id: int | None,
    ) -> dict[str, Any] | None:
        if not isinstance(repository, dict):
            return None

        raw_name = repository.get("name")
        if isinstance(raw_name, str) and raw_name:
            repository_path = raw_name
        else:
            repository_path = (
                f"{project_name}/{repository.get('repository_name', '')}".rstrip("/")
            )

        if not repository_path:
            return None

        repository_name = repository_path.split("/", 1)[-1]

        if self.name_prefix and not repository_name.lower().startswith(
            self.name_prefix
        ):
            return None
        if self.name_contains and self.name_contains not in repository_name.lower():
            return None

        artifact_count = _coerce_int(
            repository.get("artifact_count") or repository.get("artifactCount")
        )
        pull_count = _coerce_int(
            repository.get("pull_count") or repository.get("pullCount")
        )

        creation_time = repository.get("creation_time") or repository.get(
            "creationTime"
        )
        update_time = repository.get("update_time") or repository.get("updateTime")

        return {
            "repository_id": repository.get("id"),
            "project_id": project_id,
            "project_name": project_name,
            "repository_name": repository_name,
            "repository_path": repository_path,
            "artifact_count": artifact_count,
            "pull_count": pull_count,
            "creation_time": creation_time,
            "update_time": update_time,
        }


def _coerce_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
