"""Incremental-resync flows, used by ``main.py`` when a run has a cursor.

Each ``build_incremental_*_params`` builds the query for a run that has a cursor:
the cursor strategy's ``merge_params`` swaps the selector's ``TIMESTAMP_SELECTORS``
for the cursor filter.
The matching full-resync builders live in ``gitlab/clients/utils.py``.

Kinds the cursor can't be expressed for as a query param (skills, plugins) get
their own ``resync_*_incremental`` flow here; the full flows live in
``gitlab/helpers/skill_plugin_resync.py``. Resync handlers in ``main.py`` pick one
or the other on ``sync_cursor``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from port_ocean.core.incremental.strategies import ServerSideTimestampStrategy
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from gitlab.clients.gitlab_client import GitLabClient
from gitlab.clients.options import IssueOptions
from gitlab.clients.utils import (
    MergeRequestState,
    build_issue_params,
    build_pipeline_params,
    build_project_params,
)
from gitlab.helpers.skill_folder import find_owning_skill_md_paths
from gitlab.helpers.utils import build_search_query, changed_files
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
from integration import GitLabPluginSelector, GitLabSkillSelector

# Selector time filters the cursor replaces on every incremental run.
TIMESTAMP_SELECTORS = {
    "finished_after",
    "finished_before",
    "updated_after",
    "updated_before",
}

# GitLab filters list endpoints server-side by the resource's updated_at.
UPDATED_AFTER_INCREMENTAL = ServerSideTimestampStrategy(
    param_key="updated_after", replaces=TIMESTAMP_SELECTORS
)
LAST_ACTIVITY_AFTER_INCREMENTAL = ServerSideTimestampStrategy(
    param_key="last_activity_after", replaces=TIMESTAMP_SELECTORS
)


def build_project_list_params(
    include_only_active_projects: bool | None,
    cursor: datetime | None,
) -> dict[str, Any]:
    """Query params for ``GET /projects``.

    With a cursor, adds ``last_activity_after``; without one, the base params pass through.
    """
    return LAST_ACTIVITY_AFTER_INCREMENTAL.merge_params(
        build_project_params(include_only_active_projects=include_only_active_projects),
        cursor,
    )


def build_incremental_project_updated_params(
    include_only_active_projects: bool | None,
    cursor: datetime,
) -> dict[str, Any]:
    """Query params for ``GET /projects`` on an incremental run (``updated_after``).

    Used by the file, folder, skill and plugin resyncs.
    """
    params = UPDATED_AFTER_INCREMENTAL.merge_params(
        build_project_params(include_only_active_projects=include_only_active_projects),
        cursor,
    )
    params["order_by"] = "updated_at"
    return params


def build_incremental_issue_params(
    options: IssueOptions,
    cursor: datetime,
) -> dict[str, Any]:
    """Query params for ``GET /groups/{id}/issues`` on an incremental run."""
    return UPDATED_AFTER_INCREMENTAL.merge_params(
        build_issue_params(options, updated_after=None), cursor
    )


def build_incremental_merge_request_params(
    state: MergeRequestState,
    cursor: datetime,
) -> dict[str, Any]:
    """Query params for ``GET /groups/{id}/merge_requests`` on an incremental run."""
    return UPDATED_AFTER_INCREMENTAL.merge_params({"state": state}, cursor)


def build_incremental_pipeline_params(
    api_query_params: dict[str, Any] | None,
    cursor: datetime,
) -> dict[str, Any]:
    """Query params for ``GET /projects/{id}/pipelines`` on an incremental run."""
    return UPDATED_AFTER_INCREMENTAL.merge_params(
        build_pipeline_params(api_query_params), cursor
    )


def build_incremental_deployment_params(
    selector_params: dict[str, Any] | None,
    cursor: datetime,
) -> dict[str, Any]:
    """Query params for ``GET /projects/{id}/deployments`` on an incremental run.

    The selector ``order_by`` is replaced by ``order_by=updated_at``.
    """
    params = UPDATED_AFTER_INCREMENTAL.merge_params(selector_params or {}, cursor)
    params["order_by"] = "updated_at"
    return params


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
    # Same rule as the full resync: the repository tree match, then matches_skill_path.
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
