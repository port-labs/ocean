from __future__ import annotations

from urllib.parse import quote

from port_ocean.context.ocean import ocean

FOUNDRY_RESPONSE_BLUEPRINT = "foundry_response"


def port_app_base_url() -> str | None:
    configured = ocean.config.port.app_url
    if configured is not None:
        return str(configured).rstrip("/")
    api_url = str(ocean.port_client.api_url).rstrip("/")
    return api_url.replace("api.", "app.").removesuffix("/v1")


def build_entity_page_url(blueprint_identifier: str, entity_identifier: str) -> str | None:
    base = port_app_base_url()
    if not base or not entity_identifier:
        return None
    page = f"{quote(blueprint_identifier, safe='')}Entity"
    query = quote(entity_identifier, safe="")
    return f"{base}/{page}?identifier={query}"


def build_foundry_response_entity_page_url(response_id: str) -> str | None:
    if not response_id:
        return None
    return build_entity_page_url(FOUNDRY_RESPONSE_BLUEPRINT, response_id)
