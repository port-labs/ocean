from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus

from loguru import logger
from port_ocean.clients.port.types import UserAgentType
from port_ocean.clients.port.utils import handle_port_status_code
from port_ocean.context.ocean import ocean
from port_ocean.core.models import Entity

CLAUDE_SKILL_BLUEPRINT = "claude_skill"


async def fetch_skill_content(skill_identifier: str) -> dict[str, Any]:
    """Fetch instructions and resources for a Port skill from the ai-service content API.

    Returns the ``skill`` object from the response:
    ``{ name, title?, instructions, resources?: [{ path, content }] }``
    """
    response = await ocean.port_client.client.get(
        f"{ocean.port_client.api_url}/skills/{quote_plus(skill_identifier)}/content",
        headers=await ocean.port_client.auth.headers(),
    )
    handle_port_status_code(response)
    payload = response.json()
    return payload.get("skill", payload)


async def set_port_skill_relation(claude_skill_id: str, port_skill_id: str) -> None:
    """Optimistically set the portSkill relation on a claude_skill entity.

    Best-effort: failures are logged and swallowed so they never fail a run.
    """
    try:
        config = await ocean.integration.port_app_config_handler.get_port_app_config(
            use_cache=True
        )
        entity = Entity(
            identifier=claude_skill_id,
            blueprint=CLAUDE_SKILL_BLUEPRINT,
            relations={"portSkill": port_skill_id},
        )
        await ocean.port_client.upsert_entity(
            entity,
            config.get_port_request_options(),
            UserAgentType.exporter,
        )
    except Exception as error:
        logger.warning(
            f"Failed to set portSkill relation on {claude_skill_id!r} (continuing): {error}"
        )
