"""Harbor utility functions for query building and data processing."""

from typing import Any, Dict, List, Optional, NamedTuple
from enum import StrEnum
from datetime import datetime
from loguru import logger
from harbor.core.options import (
    ListProjectOptions,
    ListUserOptions,
    ListRepositoryOptions,
    ListArtifactOptions,
)


class ObjectKind(StrEnum):
    """Enum for Harbor resource kinds."""

    PROJECTS = "projects"
    REPOSITORIES = "repositories"
    USERS = "users"
    ARTIFACTS = "artifacts"


class IgnoredError(NamedTuple):
    status: int | str
    message: Optional[str] = None
    type: Optional[str] = None


def build_harbor_query_string(filters: Dict[str, Any]) -> str:
    """
    Build Harbor query string from filters.

    Harbor supports these query patterns:
    - Exact match: k=v
    - Fuzzy match: k=~v
    - Range: k=[min~max]
    - Union list: k={v1 v2 v3}
    - Intersection list: k=(v1 v2 v3)
    """
    query_parts = []

    for key, value in filters.items():
        if value is None:
            continue

        if isinstance(value, str):
            # Exact match for strings
            query_parts.append(f"{key}={value}")
        elif isinstance(value, bool):
            # Boolean values
            query_parts.append(f"{key}={str(value).lower()}")
        elif isinstance(value, (int, float)):
            # Numeric values
            query_parts.append(f"{key}={value}")
        elif isinstance(value, list):
            # List values - use union relationship
            if value:
                list_str = " ".join(str(v) for v in value)
                query_parts.append(f"{key}={{{list_str}}}")
        elif isinstance(value, tuple) and len(value) == 2:
            # Range values
            min_val, max_val = value
            query_parts.append(f"{key}=[{min_val}~{max_val}]")
        elif isinstance(value, datetime):
            # Date values
            query_parts.append(f"{key}={value.strftime('%Y-%m-%d %H:%M:%S')}")

    return ",".join(query_parts)


def build_project_params(options: ListProjectOptions) -> Dict[str, Any]:
    """Build query parameters for Harbor projects."""
    params: Dict[str, Any] = {}

    if name_prefix := options.get("name_prefix"):
        params["name"] = name_prefix

    if visibility := options.get("visibility"):
        params["public"] = visibility == "public"

    if owner := options.get("owner"):
        params["owner"] = owner

    if public := options.get("public"):
        params["public"] = public

    return params


def build_user_params(options: ListUserOptions) -> Dict[str, Any]:
    """Build query parameters for Harbor users."""
    params: Dict[str, Any] = {}

    if username_prefix := options.get("username_prefix"):
        params["username"] = username_prefix

    if email := options.get("email"):
        params["email"] = email

    if admin_only := options.get("admin_only"):
        params["admin_role_in_auth"] = admin_only

    return params


def build_repository_params(options: ListRepositoryOptions) -> Dict[str, Any]:
    """Build query parameters for Harbor repositories."""
    params: Dict[str, Any] = {}

    if project_name := options.get("project_name"):
        params["project_name"] = project_name

    if repository_name := options.get("repository_name"):
        params["q"] = f"name={repository_name}"

    if label := options.get("label"):
        if "q" in params:
            params["q"] += f",label={label}"
        else:
            params["q"] = f"label={label}"

    if q := options.get("q"):
        # Use custom query string
        params["q"] = q

    return params


def build_artifact_params(options: ListArtifactOptions) -> Dict[str, Any]:
    """Build query parameters for Harbor artifacts."""
    params: Dict[str, Any] = {}

    if project_name := options.get("project_name"):
        params["project_name"] = project_name

    if repository_name := options.get("repository_name"):
        params["repository_name"] = repository_name

    if tag := options.get("tag"):
        params["tag"] = tag

    if digest := options.get("digest"):
        params["digest"] = digest

    if label := options.get("label"):
        params["label"] = label

    if media_type := options.get("media_type"):
        params["type"] = media_type

    if created_since := options.get("created_since"):
        if isinstance(created_since, str):
            params["creation_time"] = created_since
        elif isinstance(created_since, datetime):
            params["creation_time"] = created_since.strftime("%Y-%m-%d %H:%M:%S")

    if severity_threshold := options.get("severity_threshold"):
        params["with_scan_overview"] = True
        params["severity"] = severity_threshold

    if with_scan_overview := options.get("with_scan_overview"):
        params["with_scan_overview"] = with_scan_overview

    if q := options.get("q"):
        # Use custom query string
        params["q"] = q

    return params


def create_search_params(items: List[str], batch_size: int = 10) -> List[str]:
    """
    Create search parameters for Harbor queries
    """
    search_params = []

    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]
        # Create union query for Harbor: name={item1 item2 item3}
        search_string = f"name={{{' '.join(batch)}}}"
        search_params.append(search_string)
        logger.debug(f"Created search parameter: {search_string}")

    return search_params


def enrich_with_project(
    response: Dict[str, Any], project_name: str, key: str = "__project"
) -> Dict[str, Any]:
    """Helper function to enrich response with project information.

    Args:
        response: The response to enrich
        project_name: The name of the project
        key: The key to use for project information (defaults to "__project")

    Returns:
        The enriched response
    """
    response[key] = project_name
    return response


def enrich_with_repository(
    response: Dict[str, Any], repository_name: str, key: str = "__repository"
) -> Dict[str, Any]:
    """Helper function to enrich response with repository information.

    Args:
        response: The response to enrich
        repository_name: The name of the repository
        key: The key to use for repository information (defaults to "__repository")

    Returns:
        The enriched response
    """
    response[key] = repository_name
    return response


def enrich_artifacts_with_context(
    artifacts: List[Dict[str, Any]], project_name: str, repository_name: str
) -> List[Dict[str, Any]]:
    """Enrich artifacts with project and repository context.

    Args:
        artifacts: List of artifacts to enrich
        project_name: The project name
        repository_name: The repository name

    Returns:
        List of enriched artifacts
    """
    for artifact in artifacts:
        artifact["project_name"] = project_name
        artifact["repository_name"] = repository_name

    return artifacts
