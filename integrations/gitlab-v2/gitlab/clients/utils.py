from datetime import datetime
from port_ocean.context.event import event
from integration import BranchSelector, GitlabPortAppConfig
from gitlab.clients.options import IssueOptions
from typing import Literal, cast, Any, Optional

MergeRequestState = Literal["opened", "closed", "merged"]


def get_visibility_config() -> tuple[bool, int]:
    """Helper function to get visibility configuration from port_app_config.

    Returns:
        Tuple of (use_min_access_level, min_access_level)
    """
    port_app_config = cast(GitlabPortAppConfig, event.port_app_config)
    use_min_access_level = bool(port_app_config.visibility.use_min_access_level)
    min_access_level = int(port_app_config.visibility.min_access_level)
    return use_min_access_level, min_access_level


def build_visibility_params() -> dict[str, Any]:
    """Helper function to build params dictionary based on visibility configuration.

    Returns:
        Dictionary of parameters to pass to GitLab API calls
    """
    use_min_access_level, min_access_level = get_visibility_config()
    if use_min_access_level:
        return {"min_access_level": min_access_level}
    return {}


def build_group_params(
    include_only_active_groups: Optional[bool] = None,
) -> dict[str, Any]:
    """Helper function to build params dictionary to filter groups.

    Returns:
        Dictionary of parameters to pass to GitLab API calls
    """
    visibility_params = build_visibility_params()
    params: dict[str, Any] = {}
    params.update(visibility_params)
    if include_only_active_groups is not None:
        params["active"] = include_only_active_groups
    return params


def build_project_params(
    include_only_active_projects: Optional[bool] = None,
) -> dict[str, Any]:
    """Helper function to build params dictionary to filter projects.

    Returns:
        Dictionary of parameters to pass to GitLab API calls
    """
    visibility_params = build_visibility_params()
    params: dict[str, Any] = {}
    params.update(visibility_params)
    if include_only_active_projects is not None:
        params["active"] = include_only_active_projects
    return params


def build_issue_params(
    options: IssueOptions,
    updated_after: Optional[datetime],
) -> dict[str, Any]:
    """Query params for ``GET /groups/{id}/issues`` on a full resync."""
    params: dict[str, Any] = {
        key: value
        for key, value in options.items()
        if value is not None and key != "updated_after"
    }
    if updated_after is not None:
        params["updated_after"] = updated_after.isoformat()
    return params


def build_merge_request_params(
    state: MergeRequestState,
    lookback_updated_after: datetime | None,
) -> dict[str, Any]:
    """Query params for ``GET /groups/{id}/merge_requests`` on a full resync.

    ``opened`` MRs are fetched without a time filter; other states use the lookback.
    """
    params: dict[str, Any] = {"state": state}
    effective = lookback_updated_after if state != "opened" else None
    if effective is not None:
        params["updated_after"] = effective.isoformat()
    return params


def build_pipeline_params(
    api_query_params: dict[str, Any] | None,
) -> dict[str, Any]:
    """Query params for ``GET /projects/{id}/pipelines`` on a full resync.

    A selector ``updated_after`` (ISO string) is passed through as an ISO timestamp.
    """
    raw = dict(api_query_params or {})
    selector_updated_after = parse_optional_iso_datetime(raw.pop("updated_after", None))
    params: dict[str, Any] = {
        key: value for key, value in raw.items() if value is not None
    }
    if selector_updated_after is not None:
        params["updated_after"] = selector_updated_after.isoformat()
    return params


def parse_optional_iso_datetime(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def build_branch_params(branch_selector: BranchSelector) -> dict[str, Any]:
    """Build params dictionary to filter branches for a GitLab project.

    Supports filtering by regex or search string. regex and search are mutually
    exclusive — if regex is set it takes precedence and search is ignored.

    Args:
        branch_selector: Branch selector containing optional regex and search filters.

    Returns:
        Dictionary of parameters to pass to GitLab API calls.
    """
    params: dict[str, Any] = {}
    if branch_selector.regex is not None:
        params["regex"] = branch_selector.regex
        return params

    if branch_selector.search is not None:
        params["search"] = branch_selector.search
        return params

    return params
