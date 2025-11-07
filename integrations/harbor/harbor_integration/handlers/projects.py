"""Handler for retrieving and filtering Harbor projects."""

from typing import List, AsyncGenerator, Dict, Any

from ..client import HarborClient
from ..config import HarborConfig
from ..core.models import HarborProject


async def get_projects(
    client: HarborClient, config: HarborConfig
) -> AsyncGenerator[List[Dict[str, Any]], None]:
    """
    Retrieve and filter Harbor projects based on configuration.
    Args:
        client (HarborClient): Harbor API client.
        config (HarborConfig): Configuration settings.
    Returns:
        AsyncGenerator[List[Dict[str, Any]], None]: Batches of raw project data.
    """

    async for projects_batch in client.get_projects():
        batch_entities = []
        for project_data in projects_batch:
            project = HarborProject(**project_data)
            if not _should_include_project(project, config):
                continue
            batch_entities.append(_map_project_to_entity(project))

        if batch_entities:
            yield batch_entities


def _should_include_project(project: HarborProject, config: HarborConfig) -> bool:
    """
    Determine if a project should be included based on the configuration.
    Args:
        project (HarborProject): The Harbor project to evaluate.
        config (HarborConfig): Configuration settings for filtering.
    Returns:
        bool: True if the project should be included, False otherwise.
    """

    if config.project_name_prefix and not project.name.startswith(
        config.project_name_prefix
    ):
        return False
    is_public = project.metadata and project.metadata.get("public") == "true"
    if is_public and not config.include_public_projects:
        return False
    if not is_public and not config.include_private_projects:
        return False
    return True


def _map_project_to_entity(project: HarborProject) -> Dict[str, Any]:
    """
    Map a HarborProject to a generic Entity.
    Args:
        project (HarborProject): The Harbor project to map.
    Returns:
        Dict[str, Any]
    """

    is_public = project.metadata and project.metadata.get("public") == "true"

    return {
        "projectId": project.project_id,
        "name": project.name,
        "ownerName": project.owner_name,
        "creationTime": project.creation_time.isoformat()
        if project.creation_time
        else None,
        "updatedTime": project.update_time.isoformat() if project.update_time else None,
        "repoCount": project.repo_count,
        "isPublic": is_public,
        "deleted": project.deleted,
        "metadata": project.metadata,
    }
