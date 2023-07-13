import asyncio
from typing import Type, Any

import httpx
from starlette import status

from port_ocean.clients.port.client import PortClient
from port_ocean.core.handlers.port_app_config.models import PortAppConfig
from port_ocean.utils import get_port_defaults


async def _is_integration_exists(port_client: PortClient) -> bool:
    try:
        await port_client.get_current_integration()
    except httpx.HTTPStatusError as e:
        if e.response.status_code != status.HTTP_404_NOT_FOUND:
            raise e

        return False

    return True


def deconstruct_blueprints(
    raw_blueprints: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], ...]:
    all_blueprints = []
    all_relations = []
    all_mirror = []
    all_calculated = []
    for blueprint in raw_blueprints.copy():
        all_calculated = []
        blueprint.pop("calculated", [])

        all_mirror.append(blueprint.copy())
        blueprint.pop("mirror", [])

        all_relations.append(blueprint.copy())
        blueprint.pop("relations", [])

        all_blueprints.append(blueprint)

    return all_blueprints, all_relations, all_mirror, all_calculated


async def initialize_defaults(
    config_class: Type[PortAppConfig], port_client: PortClient
) -> None:
    is_exists = await _is_integration_exists(port_client)
    if is_exists:
        return None
    defaults = get_port_defaults(config_class)
    if not defaults:
        return None

    blueprint_creation_stage, *blueprint_patches = deconstruct_blueprints(
        defaults.blueprints
    )

    async with httpx.AsyncClient() as client:  # type: httpx.AsyncClient
        await asyncio.gather(
            *[
                port_client.create_blueprint(blueprint)
                for blueprint in blueprint_creation_stage
            ]
        )

        for patch_stage in blueprint_patches:
            await asyncio.gather(
                *[
                    port_client.patch_blueprint(blueprint["identifier"], blueprint)
                    for blueprint in patch_stage
                ]
            )

        await asyncio.gather(
            *[
                port_client.create_action(blueprint_actions["blueprint"], action)
                for blueprint_actions in defaults.actions
                for action in blueprint_actions["data"]
            ]
        )

        await asyncio.gather(
            *[
                port_client.create_scorecard(blueprint_scorecards["blueprint"], action)
                for blueprint_scorecards in defaults.scorecards
                for action in blueprint_scorecards["data"]
            ]
        )
