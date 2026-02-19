"""Handler for retrieving and filtering Harbor projects."""

from typing import List, AsyncGenerator, Dict, Any

from ..client import HarborClient
from ..config import HarborConfig
from ..core.models import HarborProject

from ..core.logger import logger


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
            logger.debug("project_batch: {}", batch_entities)
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
    logger.debug("Mapping project to entity: {}", project)

    return {
        "project_id": project.project_id,
        "name": project.name,
        "owner_id": project.owner_id,
        "owner_name": project.owner_name,
        "registry_id": project.registry_id,
        "repo_count": project.repo_count,
        "is_public": project.is_public,
        "togglable": project.togglable,
        "deleted": project.deleted,
        "creation_time": project.creation_time.isoformat()
        if project.creation_time
        else None,
        "update_time": project.update_time.isoformat() if project.update_time else None,
    }
