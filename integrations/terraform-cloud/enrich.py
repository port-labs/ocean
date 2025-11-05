from asyncio import gather
from typing import Any, List
from loguru import logger

from client import TerraformClient


async def enrich_state_versions_with_output_data(
    http_client: TerraformClient, state_versions: List[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Enriches the state versions with output data."""

    async def fetch_output(state_version: dict[str, Any]) -> dict[str, Any]:
        try:
            output = await http_client.get_state_version_output(state_version["id"])
            return {**state_version, "__output": output}
        except Exception as e:
            logger.warning(
                f"Failed to fetch output for state version {state_version['id']}: {e}"
            )
            return {**state_version, "__output": {}}

    enriched_versions = await gather(
        *[fetch_output(state_version) for state_version in state_versions]
    )
    return list(enriched_versions)


async def enrich_workspaces_with_tags(
    http_client: TerraformClient, workspaces: List[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Enriches workspaces with their tags."""

    async def get_tags_for_workspace(workspace: dict[str, Any]) -> dict[str, Any]:
        try:
            tags = []
            async for tag_batch in http_client.get_workspace_tags(workspace["id"]):
                tags.extend(tag_batch)
            return {**workspace, "__tags": tags}
        except Exception as e:
            logger.warning(f"Failed to fetch tags for workspace {workspace['id']}: {e}")
            return {**workspace, "__tags": []}

    enriched_workspaces = await gather(
        *[get_tags_for_workspace(workspace) for workspace in workspaces]
    )
    return list(enriched_workspaces)


async def enrich_workspace_with_tags(
    http_client: TerraformClient, workspace: dict[str, Any]
) -> dict[str, Any]:
    """Enriches a single workspace with its tags."""
    try:
        tags = []
        async for tag_batch in http_client.get_workspace_tags(workspace["id"]):
            tags.extend(tag_batch)
        return {**workspace, "__tags": tags}
    except Exception as e:
        logger.warning(f"Failed to fetch tags for workspace {workspace['id']}: {e}")
        return {**workspace, "__tags": []}
