import asyncio
import json
from pathlib import Path
from typing import Type, Any, TypedDict, Optional

import httpx
import yaml
from loguru import logger
from pydantic import BaseModel, Field
from starlette import status

from port_ocean.clients.port.client import PortClient
from port_ocean.config.settings import IntegrationConfiguration
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.port_app_config.models import PortAppConfig
from port_ocean.exceptions.port_defaults import (
    AbortDefaultCreationError,
    UnsupportedDefaultFileType,
)

YAML_EXTENSIONS = [".yaml", ".yml"]
ALLOWED_FILE_TYPES = [".json", *YAML_EXTENSIONS]


class Preset(TypedDict):
    blueprint: str
    data: list[dict[str, Any]]


class Defaults(BaseModel):
    blueprints: list[dict[str, Any]] = []
    actions: list[Preset] = []
    scorecards: list[Preset] = []
    port_app_config: Optional[PortAppConfig] = Field(
        default=None, alias="port-app-config"
    )

    class Config:
        allow_population_by_field_name = True


async def _is_integration_exists(port_client: PortClient) -> bool:
    try:
        await port_client.get_current_integration()
        return True
    except httpx.HTTPStatusError as e:
        if e.response.status_code != status.HTTP_404_NOT_FOUND:
            raise e

    return False


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
    creation_stage, *blueprint_patches = deconstruct_blueprints_to_creation_steps(
        defaults.blueprints
    )

    create_results = await asyncio.gather(
        *(port_client.create_blueprint(blueprint) for blueprint in creation_stage),
        return_exceptions=True,
    )

    errors = [result for result in create_results if isinstance(result, Exception)]
    created_blueprints = [
        result["identifier"]
        for result in create_results
        if not isinstance(result, Exception)
    ]

    if errors:
        for error in errors:
            if isinstance(error, httpx.HTTPStatusError):
                logger.warning(
                    f"Failed to create resources: {error.response.text}. Rolling back changes..."
                )

        raise AbortDefaultCreationError(created_blueprints, errors)

    try:
        for patch_stage in blueprint_patches:
            await asyncio.gather(
                *(
                    port_client.patch_blueprint(blueprint["identifier"], blueprint)
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

        await port_client.initialize_integration(
            integration_config.integration.type,
            integration_config.event_listener.to_request(),
            port_app_config=defaults.port_app_config,
        )
    except httpx.HTTPStatusError as e:
        logger.error(
            f"Failed to create resources: {e.response.text}. Rolling back changes..."
        )
        raise AbortDefaultCreationError(created_blueprints, [e])


async def _initialize_defaults(
    config_class: Type[PortAppConfig], integration_config: IntegrationConfiguration
) -> None:
    port_client = ocean.port_client
    is_exists = await _is_integration_exists(port_client)
    if is_exists:
        return None
    defaults = get_port_integration_defaults(config_class)
    if not defaults:
        return None

    try:
        await _create_resources(port_client, defaults, integration_config)
    except AbortDefaultCreationError as e:
        logger.warning(
            f"Failed to create resources. Rolling back blueprints : {e.blueprints_to_rollback}"
        )
        await asyncio.gather(
            *(
                port_client.delete_blueprint(
                    blueprint["identifier"], should_raise=False
                )
                for blueprint in defaults.blueprints
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


def get_port_integration_defaults(
    port_app_config_class: Type[PortAppConfig], base_path: Path = Path(".")
) -> Defaults | None:
    defaults_dir = base_path / ".port/resources"
    if not defaults_dir.exists():
        return None

    if not defaults_dir.is_dir():
        raise UnsupportedDefaultFileType(
            f"Defaults directory is not a directory: {defaults_dir}"
        )

    default_jsons = {}
    allowed_file_names = [
        field_model.alias for _, field_model in Defaults.__fields__.items()
    ]
    for path in defaults_dir.iterdir():
        if path.stem in allowed_file_names:
            if not path.is_file() or path.suffix not in ALLOWED_FILE_TYPES:
                raise UnsupportedDefaultFileType(
                    f"Defaults directory should contain only one of the next types: {ALLOWED_FILE_TYPES}. Found: {path}"
                )

            if path.suffix in YAML_EXTENSIONS:
                default_jsons[path.stem] = yaml.safe_load(path.read_text())
            else:
                default_jsons[path.stem] = json.loads(path.read_text())

    return Defaults(
        blueprints=default_jsons.get("blueprints", []),
        actions=default_jsons.get("actions", []),
        scorecards=default_jsons.get("scorecards", []),
        port_app_config=port_app_config_class(
            **default_jsons.get("port-app-config", {})
        ),
    )
