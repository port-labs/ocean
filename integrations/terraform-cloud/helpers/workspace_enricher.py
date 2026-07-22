from asyncio import gather
from typing import Any, List
from loguru import logger

from client import TerraformClient


async def _fetch_workspace_tags(
    http_client: TerraformClient, workspace: dict[str, Any]
) -> dict[str, Any]:
    """Fetches tags for a single workspace."""
    try:
        tags = []
        async for tag_batch in http_client.get_workspace_tags(workspace["id"]):
            tags.extend(tag_batch)
        return {**workspace, "__tags": tags}
    except Exception as e:
        logger.warning(f"Failed to fetch tags for workspace {workspace['id']}: {e}")
        return {**workspace, "__tags": []}


async def enrich_workspaces_with_tags(
    http_client: TerraformClient, workspaces: List[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Enriches workspaces with their tags."""
    enriched_workspaces = await gather(
        *[_fetch_workspace_tags(http_client, workspace) for workspace in workspaces]
    )
    return list(enriched_workspaces)


async def enrich_workspace_with_tags(
    http_client: TerraformClient, workspace: dict[str, Any]
) -> dict[str, Any]:
    """Enriches a single workspace with its tags."""
    return await _fetch_workspace_tags(http_client, workspace)
