from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional, Sequence

from loguru import logger
from port_ocean.core.incremental.strategies import ServerSideTimestampStrategy
from port_ocean.utils.time import convert_str_to_utc_datetime

from gitlab.clients.gitlab_client import GitLabClient
from gitlab.clients.options import IssueOptions

# GitLab filters list endpoints server-side by the resource's updated_at.
UPDATED_AFTER_INCREMENTAL = ServerSideTimestampStrategy(param_key="updated_after")
LAST_ACTIVITY_AFTER_INCREMENTAL = ServerSideTimestampStrategy(
    param_key="last_activity_after"
)

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


def build_file_project_params(
    base_params: dict[str, Any],
    cursor: datetime | None,
) -> dict[str, Any]:
    """Query params for the file kind's ``GET /projects`` list."""
    params = UPDATED_AFTER_INCREMENTAL.merge_params(base_params, cursor)
    if "updated_after" in params:
        params["order_by"] = "updated_at"
    return params


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


def build_deployment_params(
    api_query_params: dict[str, Any] | None,
    cursor: datetime | None,
) -> dict[str, Any]:
    """Query params for ``GET /projects/{id}/deployments``."""
    raw = dict(api_query_params or {})
    if "finished_after" in raw or "finished_before" in raw:
        # GitLab rejects mixing a finished window with updated_after.
        raw.pop("updated_after", None)
        params = {key: value for key, value in raw.items() if value is not None}
        params["order_by"] = "finished_at"
        return params

    params = merge_updated_after_params(api_query_params, cursor)
    if "updated_after" in params:
        params["order_by"] = "updated_at"
    return params


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


def project_updated_before_cursor(project: dict[str, Any], cursor: datetime) -> bool:
    """True when the project row has not changed since ``cursor``.

    A missing ``updated_at`` does not skip the project; the commit list decides.
    """
    raw = project.get("updated_at")
    if not isinstance(raw, str) or not raw:
        return False
    updated = convert_str_to_utc_datetime(raw)
    if cursor.tzinfo is None:
        cursor = cursor.replace(tzinfo=timezone.utc)
    return updated < cursor.astimezone(timezone.utc)


def oldest_commit_parent(commits: list[dict[str, Any]]) -> str | None:
    """First parent of the oldest commit in a newest-first list.

    ``None`` means that commit has no parent (the root of the branch).
    """
    if not commits:
        return None
    parents = commits[-1].get("parent_ids") or []
    if not parents or not isinstance(parents[0], str) or not parents[0]:
        return None
    return parents[0]


def compare_is_incomplete(compare: dict[str, Any] | None) -> bool:
    """True when the compare file list cannot be trusted.

    ``compare_timeout`` means GitLab hit a size or time limit and ``diffs`` may
    be missing files. ``too_large`` and ``collapsed`` only omit patch text.
    """
    if not compare or compare.get("compare_timeout"):
        return True
    return compare.get("diffs") is None


def changed_paths_from_diffs(diffs: list[dict[str, Any]]) -> set[str]:
    """Added or edited paths from a compare. Deleted paths are left out."""
    changed: set[str] = set()
    for diff in diffs:
        if diff.get("deleted_file"):
            continue
        new_path = diff.get("new_path")
        if isinstance(new_path, str) and new_path:
            changed.add(new_path)
    return changed


def included_path_changed(changed: set[str], included_files: Sequence[str]) -> bool:
    if not included_files:
        return False
    included = set(included_files)
    return any(path in included for path in changed)


async def load_named_projects(
    client: GitLabClient,
    repositories: Sequence[str],
    cursor: datetime,
) -> list[dict[str, Any]]:
    """Fetch named repos and drop those whose ``updated_at`` is before ``cursor``."""
    projects: list[dict[str, Any]] = []
    for repo in repositories:
        project = await client.get_project(repo)
        if not project or not project.get("default_branch"):
            continue
        if project_updated_before_cursor(project, cursor):
            logger.info(
                f"Skipping project '{repo}' during incremental sync: "
                "updated_at is before the cursor"
            )
            continue
        projects.append(project)
    return projects
