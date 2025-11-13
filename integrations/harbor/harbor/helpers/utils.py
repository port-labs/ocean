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

    if q := options.get("q"):
        params["q"] = q

    if sort := options.get("sort"):
        params["sort"] = sort

    return params


def build_user_params(options: ListUserOptions) -> Dict[str, Any]:
    """Build query parameters for Harbor users."""
    params: Dict[str, Any] = {}

    if q := options.get("q"):
        params["q"] = q

    if sort := options.get("sort"):
        params["sort"] = sort

    return params


def build_repository_params(options: ListRepositoryOptions) -> Dict[str, Any]:
    """Build query parameters for Harbor repositories."""
    params: Dict[str, Any] = {}

    if q := options.get("q"):
        params["q"] = q

    if sort := options.get("sort"):
        params["sort"] = sort

    return params


def build_artifact_params(options: ListArtifactOptions) -> Dict[str, Any]:
    """Build query parameters for Harbor artifacts."""
    params: Dict[str, Any] = {}

    if q := options.get("q"):
        params["q"] = q

    if sort := options.get("sort"):
        params["sort"] = sort

    if with_tag := options.get("with_tag"):
        params["with_tag"] = with_tag

    if with_label := options.get("with_label"):
        params["with_label"] = with_label

    if with_scan_overview := options.get("with_scan_overview"):
        params["with_scan_overview"] = with_scan_overview

    if with_sbom_overview := options.get("with_sbom_overview"):
        params["with_sbom_overview"] = with_sbom_overview

    if with_signature := options.get("with_signature"):
        params["with_signature"] = with_signature

    if with_immutable_status := options.get("with_immutable_status"):
        params["with_immutable_status"] = with_immutable_status

    if with_accessory := options.get("with_accessory"):
        params["with_accessory"] = with_accessory

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
