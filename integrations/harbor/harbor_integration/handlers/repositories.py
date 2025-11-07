"""Handler for retrieving and filtering Harbor project repositories."""

from typing import List, Dict, Any, AsyncGenerator

from ..client import HarborClient
from ..config import HarborConfig
from ..core.models import HarborRepository


async def get_repositories(
    client: HarborClient, config: HarborConfig
) -> AsyncGenerator[List[Dict[str, Any]], None]:
    """
    Retrieve and filter Harbor project repositories based on configuration.
    Args:
        client (HarborClient): Harbor API client.
        config (HarboarConfig): Configuration settings.
    Returns:
        AsyncGenerator[List[Dict[str, Any]], None]
    """

    async for project_batch in client.get_projects():
        for project_data in project_batch:
            project_name = project_data["name"]

            async for repo_batch in client.get_repositories(project_name):
                batch_entities = []
                for repo_data in repo_batch:
                    repository = HarborRepository(**repo_data)
                    entity = _map_repository_to_entity(repository, project_name)
                    batch_entities.append(entity)

                if batch_entities:
                    yield batch_entities


def _map_repository_to_entity(
    repository: HarborRepository, project_name: str
) -> Dict[str, Any]:
    repo_short_name = (
        repository.name.split("/")[-1] if "/" in repository.name else repository.name
    )

    return {
        "id": repository.id,
        "name": repo_short_name,
        "fullName": repository.name,
        "projectId": repository.project_id,
        "projectName": project_name,
        "description": repository.description,
        "artifactCount": repository.artifact_count,
        "pullCount": repository.pull_count,
        "creationTime": repository.creation_time.isoformat()
        if repository.creation_time
        else None,
        "updateTime": repository.update_time.isoformat()
        if repository.update_time
        else None,
    }
