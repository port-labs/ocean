from datetime import datetime, timedelta, timezone
from typing import Any

from loguru import logger

from integrations.harbor.exporters import (
    ArtifactsExporter,
    ProjectsExporter,
    RepositoriesExporter,
    UsersExporter,
)
from integrations.harbor.integration import get_runtime
from integrations.harbor.logging_utils import (
    HarborLogContext,
    configure_harbor_logger,
    log_resync_summary,
    with_org_context,
)
from integrations.harbor.mappers import (
    map_artifact,
    map_project,
    map_repository,
    map_user,
)
from port_ocean.context.ocean import ocean


def _now_with_offset(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def _artifact_identifier(project_name: str, repository: str, digest: str) -> str:
    return f"{project_name}/{repository}@{digest}"


SAMPLE_ARTIFACTS: list[dict[str, Any]] = [
    {
        "project_name": "harbor-project-demo",
        "repository": "library/nginx",
        "repository_path": "harbor-project-demo/library/nginx",
        "digest": "sha256:f4e1c7fca5a0d8b1",
        "artifact_type": "image",
        "media_type": "application/vnd.oci.image.manifest.v1+json",
        "tag_count": 2,
        "primary_tag": "latest",
        "labels": ["env:demo"],
        "created_at": _now_with_offset(days=2),
        "pushed_at": _now_with_offset(days=1),
        "vulnerability_severity": "Medium",
        "critical_vulnerability_count": 0,
        "high_vulnerability_count": 1,
        "medium_vulnerability_count": 2,
        "low_vulnerability_count": 0,
        "negligible_vulnerability_count": 0,
        "scan_completed_at": _now_with_offset(days=1),
        "artifact_identifier": _artifact_identifier(
            "harbor-project-demo",
            "library/nginx",
            "sha256:f4e1c7fca5a0d8b1",
        ),
    },
    {
        "project_name": "harbor-project-sre",
        "repository": "charts/external-dns",
        "repository_path": "harbor-project-sre/charts/external-dns",
        "digest": "sha256:9ab12c3def098765",
        "artifact_type": "helm-chart",
        "media_type": "application/vnd.cncf.helm.chart.v1+json",
        "tag_count": 1,
        "primary_tag": "1.13.1",
        "labels": ["team:sre"],
        "created_at": _now_with_offset(days=3),
        "pushed_at": _now_with_offset(days=2),
        "vulnerability_severity": "Low",
        "critical_vulnerability_count": 0,
        "high_vulnerability_count": 0,
        "medium_vulnerability_count": 0,
        "low_vulnerability_count": 1,
        "negligible_vulnerability_count": 0,
        "scan_completed_at": _now_with_offset(days=2),
        "artifact_identifier": _artifact_identifier(
            "harbor-project-sre",
            "charts/external-dns",
            "sha256:9ab12c3def098765",
        ),
    },
]

SAMPLE_VULNERABILITIES: list[dict[str, Any]] = [
    {
        "vulnerability_id": "CVE-2024-1234",
        "severity": "High",
        "package": "openssl",
        "current_version": "1.1.1g",
        "fix_version": "1.1.1w",
        "score": 7.8,
        "scanner": "Trivy",
        "status": "Open",
        "artifact_identifier": SAMPLE_ARTIFACTS[0]["artifact_identifier"],
    },
    {
        "vulnerability_id": "CVE-2023-5555",
        "severity": "Medium",
        "package": "glibc",
        "current_version": "2.31",
        "fix_version": "2.37",
        "score": 6.2,
        "scanner": "Anchore",
        "status": "Ignored",
        "artifact_identifier": SAMPLE_ARTIFACTS[-1]["artifact_identifier"],
    },
]


@ocean.on_resync()
async def on_resync(kind: str) -> list[dict[Any, Any]]:
    """Resync handler for Harbor integration."""
    runtime = get_runtime()
    configure_harbor_logger(runtime.settings.log_level)
    organization_id = runtime.resolve_port_org_id()
    logger.info(
        "harbor.resync.start",
        **with_org_context({"kind": kind}, organization_id=organization_id),
    )

    match kind:
        case "harbor-project":
            result = await _sync_projects()
        case "harbor-user":
            result = await _sync_users()
        case "harbor-repository":
            result = await _sync_repositories()
        case "harbor-artifact":
            artifacts = await _sync_artifacts()
            result = artifacts or SAMPLE_ARTIFACTS
        case "harbor-vulnerability":
            result = SAMPLE_VULNERABILITIES
        case _:
            return []

    context = HarborLogContext()
    context.track(kind, updated=len(result))
    log_resync_summary(context, organization_id=organization_id)
    logger.info(
        "harbor.resync.done",
        **with_org_context(
            {"kind": kind, "count": len(result)}, organization_id=organization_id
        ),
    )
    return result


@ocean.on_start()
async def on_start() -> None:
    """Initial hook executed once when the integration starts."""
    print("Starting harbor integration")


async def _sync_projects() -> list[dict[str, Any]]:
    runtime = get_runtime()
    client = runtime.create_client()

    raw_projects = await _fetch_projects_raw(client, runtime)
    project_lookup = _build_project_lookup(raw_projects)

    project_memberships: dict[str, Any] = {}
    if project_lookup:
        users_exporter = UsersExporter(client, project_lookup=project_lookup)
        _, project_memberships = await users_exporter.membership_index()

    mapped_projects = [
        map_project(
            raw_project,
            (
                project_memberships.get(raw_project.get("project_name"))
                if isinstance(raw_project, dict)
                else None
            ),
        ).as_dict()
        for raw_project in raw_projects
    ]

    return mapped_projects


async def _sync_users() -> list[dict[str, Any]]:
    runtime = get_runtime()
    client = runtime.create_client()

    raw_projects = await _fetch_projects_raw(client, runtime)
    project_lookup = _build_project_lookup(raw_projects)
    exporter = UsersExporter(client, project_lookup=project_lookup)

    users: list[dict[str, Any]] = []
    async for batch in exporter.iter_users():
        for raw_user in batch:
            users.append(map_user(raw_user).as_dict())
    return users


async def _sync_artifacts() -> list[dict[str, Any]]:
    runtime = get_runtime()
    client = runtime.create_client()

    _, raw_repositories = await _collect_repositories(client, runtime)
    settings = runtime.settings

    exporter = ArtifactsExporter(
        client,
        raw_repositories,
        tag_filter=settings.artifact_tag_filter or None,
        digest_filter=settings.artifact_digest_filter or None,
        label_filter=settings.artifact_label_filter or None,
        media_type_filter=settings.artifact_media_type_filter or None,
        created_since=settings.artifact_created_since,
        vuln_severity_at_least=settings.artifact_vuln_severity_at_least,
        max_concurrency=settings.max_concurrency,
    )

    artifacts: list[dict[str, Any]] = []
    async for batch in exporter.iter_artifacts():
        for raw_artifact in batch:
            artifacts.append(map_artifact(raw_artifact).as_dict())

    return artifacts


async def _sync_repositories() -> list[dict[str, Any]]:
    runtime = get_runtime()
    client = runtime.create_client()

    mapped_repositories, _ = await _collect_repositories(client, runtime)
    return mapped_repositories


async def _collect_repositories(
    client,
    runtime,
    projects_raw: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    projects_raw = projects_raw or await _fetch_projects_raw(client, runtime)
    settings = runtime.settings

    exporter = RepositoriesExporter(
        client,
        projects_raw,
        project_filter=settings.repository_project_filter or None,
        name_prefix=settings.repository_name_prefix,
        name_contains=settings.repository_name_contains,
    )

    raw_repositories: list[dict[str, Any]] = []
    async for batch in exporter.iter_repositories():
        raw_repositories.extend(batch)

    mapped_repositories = [
        map_repository(raw_repository).as_dict() for raw_repository in raw_repositories
    ]

    return mapped_repositories, raw_repositories


def _build_project_lookup(projects: list[dict[str, Any]]) -> dict[int, str]:
    lookup: dict[int, str] = {}
    for project in projects:
        project_id = project.get("project_id")
        project_name = project.get("project_name")
        if project_id is None or not project_name:
            continue
        try:
            lookup[int(project_id)] = project_name
        except (TypeError, ValueError):
            continue
    return lookup


async def _fetch_projects_raw(
    client,
    runtime,
) -> list[dict[str, Any]]:
    settings = runtime.settings
    exporter = ProjectsExporter(
        client,
        include_names=settings.projects or None,
        visibility_filter=settings.project_visibility_filter or None,
        name_prefix=settings.project_name_prefix,
    )

    projects: list[dict[str, Any]] = []
    async for batch in exporter.iter_projects():
        projects.extend(batch)
    return projects
