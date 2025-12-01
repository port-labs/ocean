from port_ocean.context.event import event
from integration import GitlabPortAppConfig
from typing import cast, Any, Optional


def get_visibility_config() -> tuple[bool, int]:
    """Helper function to get visibility configuration from port_app_config.

    Returns:
        Tuple of (use_min_access_level, min_access_level)
    """
    port_app_config = cast(GitlabPortAppConfig, event.port_app_config)
    use_min_access_level = bool(port_app_config.visibility.use_min_access_level)
    min_access_level = int(port_app_config.visibility.min_access_level)
    return use_min_access_level, min_access_level


def get_group_query_config() -> dict[str, Any]:
    """Helper function to get group query configuration from port_app_config.

    Returns:
        Dictionary of parameters to pass to GitLab API calls
    """
    port_app_config = cast(GitlabPortAppConfig, event.port_app_config)
    return port_app_config.search.to_group_params()


def get_project_query_config() -> dict[str, Any]:
    """Helper function to get project query configuration from port_app_config.

    Returns:
        Dictionary of parameters to pass to GitLab API calls
    """
    port_app_config = cast(GitlabPortAppConfig, event.port_app_config)
    return port_app_config.search.to_project_params()


def build_visibility_params() -> dict[str, Any]:
    """Helper function to build params dictionary based on visibility configuration.

    Returns:
        Dictionary of parameters to pass to GitLab API calls
    """
    use_min_access_level, min_access_level = get_visibility_config()
    if use_min_access_level:
        return {"min_access_level": min_access_level}
    return {}


def build_group_params(include_active_groups: Optional[bool] = None) -> dict[str, Any]:
    """Helper function to build params dictionary to filter groups.

    Returns:
        Dictionary of parameters to pass to GitLab API calls
    """
    visibility_params = build_visibility_params()
    group_params = get_group_query_config()
    params: dict[str, Any] = {}
    params.update(group_params)
    params.update(visibility_params)
    if include_active_groups is not None:
        params["active"] = include_active_groups
    return params


def build_project_params() -> dict[str, Any]:
    """Helper function to build params dictionary to filter projects.

    Returns:
        Dictionary of parameters to pass to GitLab API calls
    """
    visibility_params = build_visibility_params()
    project_params = get_project_query_config()
    params: dict[str, Any] = {}
    params.update(project_params)
    params.update(visibility_params)
    return params
