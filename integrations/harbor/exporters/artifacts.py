from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, AsyncGenerator, Iterable
from urllib.parse import quote

import httpx
from loguru import logger

from integrations.harbor.client import HarborClient


class ArtifactsExporter:
    """Stream Harbor artifacts for repositories with concurrent fetch and filtering."""

    DEFAULT_CONCURRENCY = 5

    def __init__(
        self,
        client: HarborClient,
        repositories: Iterable[dict[str, Any]],
        *,
        tag_filter: Iterable[str] | None = None,
        digest_filter: Iterable[str] | None = None,
        label_filter: Iterable[str] | None = None,
        media_type_filter: Iterable[str] | None = None,
        created_since: str | None = None,
        vuln_severity_at_least: str | None = None,
        max_concurrency: int | None = None,
    ) -> None:
        self.client = client
        self.repositories: list[dict[str, str]] = []
        for repo in repositories:
            project_name = repo.get("project_name") or repo.get("project")
            repository_path = (
                repo.get("repository_path")
                or repo.get("name")
                or _build_repository_path(repo)
            )
            if not isinstance(project_name, str) or not isinstance(
                repository_path, str
            ):
                continue
            if not project_name or not repository_path:
                continue
            self.repositories.append(
                {
                    "project_name": project_name,
                    "repository_path": repository_path,
                }
            )

        self.tag_filter = _to_lower_set(tag_filter)
        self.digest_filter = _to_lower_set(digest_filter)
        self.label_filter = _to_lower_set(label_filter)
        self.media_type_filter = _to_lower_set(media_type_filter)
        self.created_since = _parse_datetime(created_since)
        self.severity_threshold = (
            _severity_rank(vuln_severity_at_least)
            if vuln_severity_at_least and vuln_severity_at_least.strip()
            else None
        )
        self.max_concurrency = max_concurrency or self.DEFAULT_CONCURRENCY

    async def iter_artifacts(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        if not self.repositories:
            return

        semaphore = asyncio.Semaphore(self.max_concurrency)
        queue: asyncio.Queue[list[dict[str, Any]] | None] = asyncio.Queue()
        sentinel = None

        async def produce(repository: dict[str, Any]) -> None:
            async with semaphore:
                try:
                    async for page in self._iter_repository_artifacts(repository):
                        if page:
                            await queue.put(page)
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code == 404:
                        # Repository exists but has no artifacts - this is normal
                        logger.debug(
                            "harbor.artifacts.empty_repository",
                            repository=repository.get("repository_path"),
                        )
                    else:
                        # Re-raise other HTTP errors
                        raise
            await queue.put(sentinel)

        tasks = [
            asyncio.create_task(produce(repository)) for repository in self.repositories
        ]

        completed = 0
        total = len(tasks)

        while completed < total:
            page = await queue.get()
            if page is sentinel:
                completed += 1
                continue
            yield page

        if tasks:
            await asyncio.gather(*tasks)

    async def _iter_repository_artifacts(
        self, repository: dict[str, Any]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        project_name = repository["project_name"]
        repository_path = repository["repository_path"]
        project_component = quote(project_name, safe="")

        # Extract repository name without project prefix
        # repository_path is like "opensource/alpine", we need just "alpine"
        repository_component = quote(repository_path, safe="")
        path = f"/projects/{project_component}/repositories/{repository_component}/artifacts"

        async for page in self.client.iter_pages(
            path,
            params={
                "with_tag": "true",
                "with_label": "true",
                "with_scan_overview": "true",
            },
        ):
            if not page:
                continue

            transformed: list[dict[str, Any]] = []
            for artifact in page:
                mapped = self._transform_artifact(
                    artifact, project_name, repository_path
                )
                if mapped is not None:
                    transformed.append(mapped)

            if transformed:
                logger.debug(
                    "harbor.artifacts.page_processed",
                    project=project_name,
                    repository=repository_path,
                    count=len(transformed),
                    input_count=len(page),
                )
                yield transformed

    def _transform_artifact(
        self,
        artifact: Any,
        project_name: str,
        repository_path: str,
    ) -> dict[str, Any] | None:
        if not isinstance(artifact, dict):
            return None

        digest = artifact.get("digest")
        if not isinstance(digest, str) or not digest:
            return None

        if self.digest_filter and digest.lower() not in self.digest_filter:
            return None

        tags = [
            tag.get("name")
            for tag in artifact.get("tags") or []
            if isinstance(tag, dict) and isinstance(tag.get("name"), str)
        ]

        if self.tag_filter and not any(tag.lower() in self.tag_filter for tag in tags):
            return None

        labels = [
            label.get("name")
            for label in artifact.get("labels") or []
            if isinstance(label, dict) and isinstance(label.get("name"), str)
        ]

        if self.label_filter and not any(
            label.lower() in self.label_filter for label in labels
        ):
            return None

        media_type = (
            artifact.get("manifest_media_type")
            or artifact.get("media_type")
            or artifact.get("type")
        )
        media_type_normalized = (
            media_type.lower() if isinstance(media_type, str) else None
        )
        if self.media_type_filter and (
            media_type_normalized not in self.media_type_filter
        ):
            return None

        creation_time = _normalize_datetime(
            artifact.get("creation_time")
            or artifact.get("created")
            or artifact.get("extra_attrs", {}).get("created")
        )

        if self.created_since and creation_time:
            created_dt = _parse_datetime(creation_time)
            if created_dt and created_dt < self.created_since:
                return None

        vulnerability = _extract_vulnerability_summary(artifact)
        if self.severity_threshold is not None and (
            _severity_rank(vulnerability["highest_severity"]) < self.severity_threshold
        ):
            return None

        project = project_name
        repository_name = repository_path.split("/", 1)[-1]
        primary_tag = tags[0] if tags else None
        pushed_at = _normalize_datetime(
            (artifact.get("push_time"))
            or (artifact.get("extra_attrs", {}).get("push_time"))
            or (artifact.get("tags") or [{}])[0].get("push_time")
        )

        artifact_entry = {
            "project_name": project,
            "repository": repository_name,
            "repository_path": repository_path,
            "digest": digest,
            "artifact_type": artifact.get("type") or artifact.get("artifact_type"),
            "media_type": media_type,
            "tag_count": len(tags),
            "primary_tag": primary_tag,
            "labels": labels,
            "created_at": creation_time,
            "pushed_at": pushed_at,
            "vulnerability_severity": vulnerability["highest_severity"],
            "critical_vulnerability_count": vulnerability["summary"].get("critical", 0),
            "high_vulnerability_count": vulnerability["summary"].get("high", 0),
            "medium_vulnerability_count": vulnerability["summary"].get("medium", 0),
            "low_vulnerability_count": vulnerability["summary"].get("low", 0),
            "negligible_vulnerability_count": vulnerability["summary"].get(
                "negligible", 0
            ),
            "scan_completed_at": vulnerability["last_scan_time"],
        }

        return artifact_entry


def _build_repository_path(repo: dict[str, Any]) -> str | None:
    project = repo.get("project_name") or repo.get("project")
    repo_name = repo.get("repository_name") or repo.get("name")
    if isinstance(project, str) and isinstance(repo_name, str):
        return f"{project}/{repo_name}".strip("/")
    return None


def _to_lower_set(values: Iterable[str] | None) -> set[str] | None:
    if not values:
        return None
    lowered = {value.strip().lower() for value in values if value and value.strip()}
    return lowered or None


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _normalize_datetime(value: str | None) -> str | None:
    dt = _parse_datetime(value)
    if not dt:
        return value
    return dt.astimezone().isoformat()


def _severity_rank(severity: str | None) -> int:
    mapping = {
        "none": 0,
        "negligible": 1,
        "low": 2,
        "medium": 3,
        "high": 4,
        "critical": 5,
    }
    if not severity:
        return 0
    return mapping.get(severity.lower(), 0)


def _extract_vulnerability_summary(artifact: dict[str, Any]) -> dict[str, Any]:
    scan_overview = artifact.get("scan_overview") or {}
    summary_counts = {
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "negligible": 0,
    }
    highest_severity = "None"
    last_scan_time: str | None = None

    for overview in scan_overview.values():
        if not isinstance(overview, dict):
            continue
        severity = overview.get("severity")
        if severity and _severity_rank(severity) > _severity_rank(highest_severity):
            highest_severity = severity.capitalize()

        summary = overview.get("summary") or {}
        for key in summary_counts:
            summary_counts[key] += int(summary.get(key, 0) or 0)

        completion = overview.get("completion_time") or overview.get("complete_time")
        completion = _normalize_datetime(completion)
        if completion and (last_scan_time is None or completion > last_scan_time):
            last_scan_time = completion

    if highest_severity == "None" and any(summary_counts.values()):
        # fallback to highest severity present in counts
        for severity in ("critical", "high", "medium", "low", "negligible"):
            if summary_counts[severity] > 0:
                highest_severity = severity.capitalize()
                break

    return {
        "highest_severity": highest_severity,
        "summary": summary_counts,
        "last_scan_time": last_scan_time,
    }
