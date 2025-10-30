"""
Helper functions for webhook processing
"""

from typing import Optional, Any
from loguru import logger

from harbor.client import HarborClient
from harbor.utils.constants import HarborKind


def extract_repository_info(
    payload: dict[str, Any],
) -> tuple[Optional[str], Optional[str]]:
    """
    Extract project name and repository name from webhook payload.

    Returns:
        Tuple of (project_name, repo_full_name) or (None, None) if not found
    """
    event_data = payload.get("event_data", {})
    repository = event_data.get("repository", {})

    project_name = repository.get("namespace")
    repo_name = repository.get("repo_full_name")

    return project_name, repo_name


def extract_deleted_resources(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Extract resources marked for deletion from webhook payload.

    Returns:
        List of resource dictionaries to be deleted
    """
    event_data = payload.get("event_data", {})
    return event_data.get("resources", [])


async def fetch_artifacts_for_repository(
    client: HarborClient, project_name: str, repo_name: str
) -> list[dict[str, Any]]:
    """
    Fetch all artifacts for a specific repository.

    Args:
        client: Harbor API client
        project_name: Project namespace
        repo_name: Full repository name

    Returns:
        List of artifact dictionaries
    """
    artifacts = []

    try:
        async for batch in client.get_paginated_resources(
            HarborKind.ARTIFACT,
            project_name=project_name,
            repository_name=repo_name,
        ):
            artifacts.extend(batch)

        logger.info(f"Fetched {len(artifacts)} artifacts from {repo_name}")
        return artifacts

    except Exception as e:
        logger.error(f"Failed to fetch artifacts for {repo_name}: {e}")
        return []


async def fetch_repository_by_name(
    client: HarborClient, project_name: str, repo_name: str
) -> list[dict[str, Any]]:
    """
    Fetch specific repository by name.

    Args:
        client: Harbor API client
        project_name: Project namespace
        repo_name: Full repository name

    Returns:
        List containing the repository dictionary (or empty if not found)
    """
    try:
        async for batch in client.get_paginated_resources(
            HarborKind.REPOSITORY, project_name=project_name
        ):
            # performantly filter to the specific repository
            matching_repos = [repo for repo in batch if repo.get("name") == repo_name]

            if matching_repos:
                logger.info(f"Found repository {repo_name}")
                return matching_repos

        logger.warning(f"Repository {repo_name} not found")
        return []

    except Exception as e:
        logger.error(f"Failed to fetch repository {repo_name}: {e}")
        return []
