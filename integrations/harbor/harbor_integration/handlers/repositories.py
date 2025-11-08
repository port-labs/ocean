"""Handler for retrieving and filtering Harbor project repositories."""

from typing import List, Dict, Any, AsyncGenerator

from ..client import HarborClient
from ..core.models import HarborRepository


async def get_repositories(
    client: HarborClient,
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
                    entity = _map_repository_to_entity(repository)
                    batch_entities.append(entity)

                if batch_entities:
                    yield batch_entities


def _map_repository_to_entity(repository: HarborRepository) -> Dict[str, Any]:
    repo_short_name = (
        repository.name.split("/")[-1] if "/" in repository.name else repository.name
    )

    return {
        "id": repository.id,
        "name": repo_short_name,
        "full_name": repository.full_name,
        "project_id": repository.project_id,
        "description": repository.description,
        "artifact_count": repository.artifact_count,
        "pull_count": repository.pull_count,
        "creation_time": repository.creation_time.isoformat()
        if repository.creation_time
        else None,
        "update_time": repository.update_time.isoformat()
        if repository.update_time
        else None,
        "project": repository.project_id,
    }
