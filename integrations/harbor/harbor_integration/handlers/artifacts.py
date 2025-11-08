"""Handler for retrieving and filtering Harbor artifacts."""

from typing import List, Dict, Any, AsyncGenerator

from ..client import HarborClient
from ..config import HarborConfig
from ..core.models import HarborArtifact


async def get_artifacts(
    client: HarborClient, config: HarborConfig
) -> AsyncGenerator[List[Dict[str, Any]], None]:
    """
    Retrieve and filter Harbor artifacts based on configuration.
    Args:
        client (HarborClient): Harbor API client.
        config (HarborConfig): Configuration settings.
    Returns:
        AsyncGenerator[List[Dict[str, Any]], None]
    """

    async for project_batch in client.get_projects():
        for project_data in project_batch:
            project_name = project_data["name"]

            async for repo_batch in client.get_repositories(project_name):
                for repo_data in repo_batch:
                    repo_name = repo_data["name"]
                    batch_entities = []

                    async for artifact_batch in client.get_artifacts(
                        project_name, repo_name
                    ):
                        for artifact_data in artifact_batch:
                            artifact = HarborArtifact(**artifact_data)

                            if not _should_include_artifact(artifact, config):
                                continue

                            entity = _map_artifact_to_entity(artifact)
                            batch_entities.append(entity)

                    if batch_entities:
                        yield batch_entities


def _should_include_artifact(artifact: HarborArtifact, config: HarborConfig) -> bool:
    """
    Determine if an artifact should be included based on the configuration.
    Args:
        artifact (HarborArtifact): The Harbor artifact to evaluate.
        config (HarborConfig): Configuration settings for filtering.
    Returns:
        bool: True if the artifact should be included, False otherwise.
    """

    if not config.min_severity:
        return True

    severity_order = ["None", "Low", "Medium", "High", "Critical"]
    artifact_severity_idx = severity_order.index(artifact.max_severity)
    min_severity_idx = severity_order.index(config.min_severity)

    return artifact_severity_idx >= min_severity_idx


def _map_artifact_to_entity(artifact: HarborArtifact) -> Dict[str, Any]:
    """
    Map a HarborArtifact to a generic Entity.
    Args:
        artifact (HarborArtifact): The Harbor artifact to map.
        project_name (str): Name of the project.
        repository_name (str): Name of the repository.
    Returns:
        Dict[str, Any]
    """

    return {
        "id": artifact.id,
        "digest": artifact.digest,
        "size": artifact.size,
        "media_type": artifact.media_type,
        "manifest_media_type": artifact.manifest_media_type,
        "push_time": artifact.push_time.isoformat(),
        "pull_time": artifact.pull_time.isoformat(),
        "tags": artifact.tag_names,
        "latest_tag": artifact.latest_tag,
        "max_severity": artifact.max_severity,
        "total_vulnerabilities": artifact.total_vulnerabilities,
        "scanners": artifact.scanner_names,
        "type": artifact.type,
        "icon": artifact.icon,
        "repository": artifact.repository_id,
    }
