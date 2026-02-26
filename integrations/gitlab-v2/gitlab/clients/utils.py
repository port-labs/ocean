from port_ocean.context.event import event
from integration import GitlabPortAppConfig
from typing import cast, Any, Optional, AsyncIterator
from loguru import logger


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


# AI! this requires the GitlabClient class, please move it to `gitlab_client` file
async def get_projects_to_scan(
    client: Any,  # GitLabClient
    repositories: Optional[list[str]] = None,
    params: Optional[dict[str, Any]] = None,
) -> AsyncIterator[list[dict[str, Any]]]:
    """Helper function to get list of projects to scan for files.

    Args:
        client: GitLabClient instance
        repositories: Optional list of repository names/IDs to limit scan to
        params: Optional parameters for group filtering

    Yields:
        List of project dictionaries
    """
    if repositories:
        projects_batch = []
        for repo in repositories:
            try:
                projects_batch.append(await client.get_project(repo))
                if len(projects_batch) >= 100:
                    yield projects_batch
                    projects_batch = []
            except Exception as e:
                logger.warning(f"Could not fetch project {repo}: {e}")
        if projects_batch:
            yield projects_batch
    else:
        async for groups_batch in client.get_parent_groups(params=params):
            for group in groups_batch:
                async for projects_batch in client.rest.get_paginated_resource(
                    f"groups/{group['id']}/projects",
                    params={"include_subgroups": True},
                ):
                    yield projects_batch
