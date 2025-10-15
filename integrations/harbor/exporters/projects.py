from __future__ import annotations

from typing import Any, AsyncGenerator, Iterable

from loguru import logger

from integrations.harbor.client import HarborClient


class ProjectsExporter:
    """Stream Harbor projects with optional filtering and mapping."""

    PROJECTS_PATH = "/projects"

    def __init__(
        self,
        client: HarborClient,
        *,
        include_names: Iterable[str] | None = None,
        visibility_filter: Iterable[str] | None = None,
        name_prefix: str | None = None,
    ) -> None:
        self.client = client
        self.include_names = {
            name.strip().lower()
            for name in (include_names or [])
            if name and name.strip()
        } or None
        self.visibility_filter = {
            visibility.strip().lower()
            for visibility in (visibility_filter or [])
            if visibility and visibility.strip()
        } or None
        self.name_prefix = name_prefix.strip().lower() if name_prefix else None

    async def iter_projects(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Yield Harbor projects in pages honouring configured filters."""
        async for page in self.client.iter_pages(
            self.PROJECTS_PATH,
            params={"with_detail": "true"},
        ):
            if not page:
                continue

            transformed = [
                mapped
                for item in page
                if (mapped := self._transform_if_included(item)) is not None
            ]

            if transformed:
                logger.debug(
                    "harbor.projects.page_processed",
                    count=len(transformed),
                    input_count=len(page),
                )
                yield transformed

    def _transform_if_included(self, item: Any) -> dict[str, Any] | None:
        if not isinstance(item, dict):
            return None

        name = item.get("name")
        if not isinstance(name, str) or not name:
            return None

        normalized_name = name.lower()
        if self.include_names and normalized_name not in self.include_names:
            return None

        if self.name_prefix and not normalized_name.startswith(self.name_prefix):
            return None

        visibility = self._extract_visibility(item)
        if self.visibility_filter and visibility not in self.visibility_filter:
            return None

        return self._map_project(item, name, visibility)

    def _map_project(
        self, project: dict[str, Any], name: str, visibility: str
    ) -> dict[str, Any]:
        repo_count = project.get("repo_count") or project.get("repository_count") or 0
        owner = project.get("owner_name") or project.get("ownerName")
        display_name = (
            project.get("metadata", {}).get("display_name")
            or project.get("display_name")
            or name
        )

        mapped = {
            "project_name": name,
            "display_name": display_name,
            "public": visibility == "public",
            "repository_count": repo_count,
            "owner": owner,
            "visibility": visibility,
            "project_id": project.get("project_id"),
        }

        return mapped

    def _extract_visibility(self, project: dict[str, Any]) -> str:
        metadata = project.get("metadata") or {}
        public_metadata = metadata.get("public")

        if isinstance(public_metadata, str):
            if public_metadata.lower() == "true":
                return "public"
            if public_metadata.lower() == "false":
                return "private"

        if isinstance(public_metadata, bool):
            return "public" if public_metadata else "private"

        # Fallback to project visibility field used by some Harbor versions
        if isinstance(project.get("public"), bool):
            return "public" if project["public"] else "private"

        if isinstance(project.get("public"), str):
            return "public" if project["public"].lower() == "true" else "private"

        return "public"
