from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from port_ocean.core.incremental.strategies import ServerSideTimestampStrategy

from gitlab.clients.gitlab_client import GitLabClient
from gitlab.clients.options import IssueOptions
from gitlab.helpers.skill_folder import find_owning_skill_md_paths
from gitlab.helpers.skill_plugin import (
    PluginProvider,
    matches_skill_path,
    path_touches_plugin,
)
from gitlab.helpers.skill_plugin_resync import (
    build_skills,
    iter_projects,
    partition_skill_patterns,
    plugins_for_projects,
)
from gitlab.helpers.utils import build_search_query, changed_files
from integration import GitLabPluginSelector, GitLabSkillSelector
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

# GitLab filters list endpoints server-side by the resource's updated_at.
UPDATED_AFTER_INCREMENTAL = ServerSideTimestampStrategy(param_key="updated_after")
LAST_ACTIVITY_AFTER_INCREMENTAL = ServerSideTimestampStrategy(
    param_key="last_activity_after"
)

# Dropped on incremental runs; replaced by cursor ``updated_after`` + ``order_by``.
TIMESTAMP_SELECTORS = {
    "finished_after",
    "finished_before",
    "updated_after",
    "updated_before",
}
MergeRequestState = Literal["opened", "closed", "merged"]


def resolve_effective_datetime(
    cursor: datetime | None,
    selector_value: datetime | None,
) -> datetime | None:
    """Prefer the incremental cursor over a selector-derived datetime."""
    if cursor is not None:
        return cursor
    return selector_value


def build_project_list_params(
    base_params: dict[str, Any],
    cursor: datetime | None,
) -> dict[str, Any]:
    """Query params for ``GET /projects``."""
    return LAST_ACTIVITY_AFTER_INCREMENTAL.merge_params(base_params, cursor)


def build_issue_params(
    options: IssueOptions,
    updated_after: Optional[datetime],
) -> dict[str, Any]:
    """Query params for ``GET /groups/{id}/issues``."""
    params = {
        key: value
        for key, value in options.items()
        if value is not None and key != "updated_after"
    }
    return UPDATED_AFTER_INCREMENTAL.merge_params(params, updated_after)


def build_merge_request_params(
    state: MergeRequestState,
    cursor: datetime | None,
    lookback_updated_after: datetime,
) -> dict[str, Any]:
    """Query params for ``GET /groups/{id}/merge_requests``."""
    params: dict[str, Any] = {"state": state}
    effective = resolve_effective_datetime(
        cursor,
        lookback_updated_after if state != "opened" else None,
    )
    return UPDATED_AFTER_INCREMENTAL.merge_params(params, effective)


def _parse_optional_iso_datetime(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def build_pipeline_params(
    api_query_params: dict[str, Any] | None,
    cursor: datetime | None,
) -> dict[str, Any]:
    """Query params for ``GET /projects/{id}/pipelines``."""
    return merge_updated_after_params(api_query_params, cursor)


def build_cursor_updated_after_params(
    api_query_params: dict[str, Any] | None,
    cursor: datetime,
) -> dict[str, Any]:
    """Drop selector timestamp filters and ``order_by``, then apply the cursor.

    Keeps non-timestamp filters. ``updated_after``, ``updated_before``,
    ``finished_after``, ``finished_before``, and ``order_by`` from the selector
    are replaced by the cursor ``updated_after`` and ``order_by=updated_at``.
    """
    params = {
        key: value
        for key, value in (api_query_params or {}).items()
        if key not in TIMESTAMP_SELECTORS and key != "order_by" and value is not None
    }
    params = UPDATED_AFTER_INCREMENTAL.merge_params(params, cursor)
    params["order_by"] = "updated_at"
    return params


def build_incremental_project_params(
    base_params: dict[str, Any],
    cursor: datetime | None,
) -> dict[str, Any]:
    """Project-list params for an incremental run.

    A cursor replaces selector timestamp filters with ``updated_after`` and
    ``order_by=updated_at``. A full resync keeps ``base_params``.
    """
    if cursor is None:
        return base_params
    return build_cursor_updated_after_params(base_params, cursor)


def merge_updated_after_params(
    api_query_params: dict[str, Any] | None,
    cursor: datetime | None,
) -> dict[str, Any]:
    raw = dict(api_query_params or {})
    selector_updated_after = _parse_optional_iso_datetime(
        raw.pop("updated_after", None)
    )
    params = {key: value for key, value in raw.items() if value is not None}
    effective = resolve_effective_datetime(cursor, selector_updated_after)
    return UPDATED_AFTER_INCREMENTAL.merge_params(params, effective)


async def resync_skills_incremental(
    client: GitLabClient,
    selector: GitLabSkillSelector,
    project_params: dict[str, Any] | None,
    since: datetime,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Rebuild only the skills whose SKILL.md or bundle files changed since ``since``.

    A project whose compare fails falls back to the full per-project search.
    """
    path_entries = selector.paths
    path_globs = [entry.path for entry in path_entries]
    patterns_by_repo, unrestricted_patterns = partition_skill_patterns(path_entries)
    repos_scope = [] if unrestricted_patterns else list(patterns_by_repo.keys())
    emitted_keys: set[str] = set()

    async for projects_batch in iter_projects(client, repos_scope, project_params):
        for project in projects_batch:
            repo = project["path_with_namespace"]
            patterns = list(
                dict.fromkeys(unrestricted_patterns + patterns_by_repo.get(repo, []))
            )
            ref = client._project_tree_ref(project)
            if not patterns or not ref:
                continue

            changed = await client.changed_paths_since(repo, since, ref)
            if changed.paths is None:
                async for files_batch in client.search_files_matching_patterns(
                    patterns, skip_parsing=True, repositories=[project]
                ):
                    skills = await build_skills(
                        client,
                        files_batch,
                        path_globs,
                        emitted_keys,
                        selector.include_skill_folder,
                    )
                    if skills:
                        yield skills
                continue

            skill_md_paths = await _changed_skill_md_paths(
                client,
                project,
                ref,
                changed.paths,
                patterns,
                selector.include_skill_folder,
            )
            if not skill_md_paths:
                continue
            files_batch = await client._process_file_batch(
                [
                    {"path": path, "ref": ref, "project_id": project["id"]}
                    for path in sorted(skill_md_paths)
                ],
                repo,
                skip_parsing=True,
            )
            skills = await build_skills(
                client,
                files_batch,
                path_globs,
                emitted_keys,
                selector.include_skill_folder,
            )
            if skills:
                yield skills


async def _changed_skill_md_paths(
    client: GitLabClient,
    project: dict[str, Any],
    ref: str,
    changed: list[str],
    patterns: list[str],
    include_skill_folder: bool,
) -> set[str]:
    """SKILL.md paths to rebuild: edited skills, plus owners of changed bundle files."""
    direct = {
        path
        for pattern in patterns
        for path in changed_files(build_search_query(pattern), changed)
        if matches_skill_path(path, patterns)
    }
    if not include_skill_folder:
        return direct
    owners = await find_owning_skill_md_paths(
        client, project, ref, set(changed), patterns
    )
    return direct | owners


async def resync_plugins_incremental(
    client: GitLabClient,
    selector: GitLabPluginSelector,
    project_params: dict[str, Any] | None,
    since: datetime,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Rebuild only the plugins of projects whose changes touch a plugin manifest or directory."""
    providers = selector.providers
    async for projects_batch in iter_projects(client, selector.repos, project_params):
        touched = [
            project
            for project in projects_batch
            if await _plugin_changed(client, project, since, providers)
        ]
        if not touched:
            continue
        batch = await plugins_for_projects(client, touched, providers)
        if batch:
            yield batch


async def _plugin_changed(
    client: GitLabClient,
    project: dict[str, Any],
    since: datetime,
    providers: list[PluginProvider],
) -> bool:
    """True when the project's plugin may have changed since ``since``.

    A failed or partial compare counts as changed, so the project is rebuilt in full.
    """
    ref = client._project_tree_ref(project)
    if not ref:
        return False
    changed = await client.changed_paths_since(
        project["path_with_namespace"], since, ref
    )
    if changed.paths is None:
        return True
    return any(path_touches_plugin(path, providers) for path in changed.paths)
