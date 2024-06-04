import asyncio
from typing import Type, Any

import httpx
from loguru import logger
from starlette import status

from port_ocean.clients.port.client import PortClient
from port_ocean.clients.port.types import UserAgentType
from port_ocean.config.settings import IntegrationConfiguration
from port_ocean.context.ocean import ocean
from port_ocean.core.defaults.common import Defaults, get_port_integration_defaults
from port_ocean.core.handlers.port_app_config.models import PortAppConfig
from port_ocean.core.models import Blueprint
from port_ocean.core.utils import gather_and_split_errors_from_results
from port_ocean.exceptions.port_defaults import (
    AbortDefaultCreationError,
)


def deconstruct_blueprints_to_creation_steps(
    raw_blueprints: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], ...]:
    """
    Deconstructing the blueprint into stages so the api wont fail to create a blueprint if there is a conflict
    example: Preventing the failure of creating a blueprint with a relation to another blueprint
    """
    (
        bare_blueprint,
        with_relations,
        full_blueprint,
    ) = ([], [], [])

    for blueprint in raw_blueprints.copy():
        full_blueprint.append(blueprint.copy())

        blueprint.pop("calculationProperties", {})
        blueprint.pop("mirrorProperties", {})
        blueprint.pop("aggregationProperties", {})
        with_relations.append(blueprint.copy())

        blueprint.pop("teamInheritance", {})
        blueprint.pop("relations", {})
        bare_blueprint.append(blueprint)

    return (
        bare_blueprint,
        with_relations,
        full_blueprint,
    )


async def _create_resources(
    port_client: PortClient,
    defaults: Defaults,
    integration_config: IntegrationConfiguration,
) -> None:
    response = await port_client._get_current_integration()
    if response.status_code == status.HTTP_404_NOT_FOUND:
        logger.info("Integration doesn't exist, creating new integration")
    else:
        logger.info("Integration already exists, skipping integration creation...")
        return

    creation_stage, *blueprint_patches = deconstruct_blueprints_to_creation_steps(
        defaults.blueprints
    )

    blueprints_results, _ = await gather_and_split_errors_from_results(
        [
            port_client.get_blueprint(blueprint["identifier"], should_log=False)
            for blueprint in creation_stage
        ],
        lambda item: isinstance(item, Blueprint),
    )

    if blueprints_results:
        logger.info(
            f"Blueprints already exist: {[result.identifier for result in blueprints_results]}. Skipping integration default creation..."
        )
        return

    created_blueprints, errors = await gather_and_split_errors_from_results(
        (
            port_client.create_blueprint(
                blueprint, user_agent_type=UserAgentType.exporter
            )
            for blueprint in creation_stage
        )
    )

    created_blueprints_identifiers = [bp["identifier"] for bp in created_blueprints]

    if errors:
        for error in errors:
            if isinstance(error, httpx.HTTPStatusError):
                logger.warning(
                    f"Failed to create resources: {error.response.text}. Rolling back changes..."
                )

        raise AbortDefaultCreationError(created_blueprints_identifiers, errors)
    created_pages_identifiers = []
    try:
        for patch_stage in blueprint_patches:
            await asyncio.gather(
                *(
                    port_client.patch_blueprint(
                        blueprint["identifier"],
                        blueprint,
                        user_agent_type=UserAgentType.exporter,
                    )
                    for blueprint in patch_stage
                )
            )

        await asyncio.gather(
            *(
                port_client.create_action(blueprint_actions["blueprint"], action)
                for blueprint_actions in defaults.actions
                for action in blueprint_actions["data"]
            )
        )

        await asyncio.gather(
            *(
                port_client.create_scorecard(blueprint_scorecards["blueprint"], action)
                for blueprint_scorecards in defaults.scorecards
                for action in blueprint_scorecards["data"]
            )
        )

        created_pages, pages_errors = await gather_and_split_errors_from_results(
            (port_client.create_page(page) for page in defaults.pages)
        )
        created_pages_identifiers = [
            page.get("identifier", "") for page in created_pages
        ]

        if pages_errors:
            for error in pages_errors:
                if isinstance(error, httpx.HTTPStatusError):
                    logger.warning(
                        f"Failed to create resources: {error.response.text}. Rolling back changes..."
                    )

            raise AbortDefaultCreationError(
                created_blueprints_identifiers,
                pages_errors,
                created_pages_identifiers,
            )

        await port_client.create_integration(
            integration_config.integration.type,
            integration_config.event_listener.to_request(),
            port_app_config=defaults.port_app_config,
        )
    except httpx.HTTPStatusError as err:
        logger.error(
            f"Failed to create resources: {err.response.text}. Rolling back changes..."
        )
        raise AbortDefaultCreationError(
            created_blueprints_identifiers, [err], created_pages_identifiers
        )


async def _initialize_defaults(
    config_class: Type[PortAppConfig], integration_config: IntegrationConfiguration
) -> None:
    port_client = ocean.port_client
    defaults = get_port_integration_defaults(config_class)
    if not defaults:
        logger.warning("No defaults found. Skipping...")
        return None

    try:
        logger.info("Found default resources, starting creation process")
        await _create_resources(port_client, defaults, integration_config)
    except AbortDefaultCreationError as e:
        logger.warning(
            f"Failed to create resources. Rolling back blueprints : {e.blueprints_to_rollback}"
        )
        await asyncio.gather(
            *(
                port_client.delete_blueprint(
                    identifier,
                    should_raise=False,
                    user_agent_type=UserAgentType.exporter,
                )
                for identifier in e.blueprints_to_rollback
            )
        )
        if e.pages_to_rollback:
            logger.warning(
                f"Failed to create resources. Rolling back pages : {e.pages_to_rollback}"
            )
            await asyncio.gather(
                *(
                    port_client.delete_page(
                        identifier,
                    )
                    for identifier in e.pages_to_rollback
                )
            )

        raise ExceptionGroup(str(e), e.errors)


def initialize_defaults(
    config_class: Type[PortAppConfig], integration_config: IntegrationConfiguration
) -> None:
    try:
        asyncio.new_event_loop().run_until_complete(
            _initialize_defaults(config_class, integration_config)
        )
    except Exception as e:
        logger.debug(f"Failed to initialize defaults, skipping... Error: {e}")
