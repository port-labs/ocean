from asyncio import gather
from typing import Any, List
from loguru import logger

from client import TerraformClient


async def fetch_state_version_output(
    http_client: TerraformClient, state_version: dict[str, Any]
) -> dict[str, Any]:
    """Fetches output data for a single state version."""
    try:
        output = await http_client.get_state_version_output(state_version["id"])
        return {**state_version, "__output": output}
    except Exception as e:
        logger.warning(
            f"Failed to fetch output for state version {state_version['id']}: {e}"
        )
        return {**state_version, "__output": {}}


async def enrich_state_versions_with_output_data(
    http_client: TerraformClient, state_versions: List[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Enriches the state versions with output data."""
    enriched_versions = await gather(
        *[
            fetch_state_version_output(http_client, state_version)
            for state_version in state_versions
        ]
    )
    return list(enriched_versions)
