from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus

from port_ocean.clients.port.utils import handle_port_status_code
from port_ocean.context.ocean import ocean
from port_ocean.core.models import Entity

CLAUDE_SKILL_BLUEPRINT = "claude_skill"
PORT_SKILL_BLUEPRINT = "_skill"


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


async def upsert_claude_skill_entity(
    claude_skill_id: str,
    port_skill_id: str,
) -> None:
    """Register or update a claude_skill entity with a relation to the Port _skill."""
    from port_ocean.clients.port.types import UserAgentType
    from port_ocean.core.handlers.port_app_config.models import PortAppConfig

    config = await ocean.integration.port_app_config_handler.get_port_app_config(
        use_cache=False
    )
    if not isinstance(config, PortAppConfig):
        raise TypeError("Expected PortAppConfig from port app config handler")

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
