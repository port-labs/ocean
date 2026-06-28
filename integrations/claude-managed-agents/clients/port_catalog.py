from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus

from port_ocean.clients.port.utils import handle_port_status_code
from port_ocean.context.ocean import ocean


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
