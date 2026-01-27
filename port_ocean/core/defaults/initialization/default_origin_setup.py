import asyncio
from typing import Type, Any

import httpx
from loguru import logger

from port_ocean.clients.port.client import PortClient
from port_ocean.clients.port.types import UserAgentType
from port_ocean.config.settings import IntegrationConfiguration
from port_ocean.core.defaults.common import Defaults, get_port_integration_defaults
from port_ocean.core.defaults.initialization.base_setup import BaseSetup
from port_ocean.core.handlers.port_app_config.models import PortAppConfig
from port_ocean.core.models import Blueprint
from port_ocean.core.utils.utils import gather_and_split_errors_from_results
from port_ocean.exceptions.port_defaults import AbortDefaultCreationError


class DefaultOriginSetup(BaseSetup):
    """Setup that creates resources including blueprints, actions, scorecards, and pages."""

    def __init__(
        self,
        port_client: PortClient,
        integration_config: IntegrationConfiguration,
        config_class: Type[PortAppConfig],
    ):
        super().__init__(port_client, integration_config, config_class)
        defaults: Defaults | None = get_port_integration_defaults(
            config_class, integration_config.resources_path
        )

        if defaults is None:
            defaults = Defaults(port_app_config=PortAppConfig(resources=[]))

        self._defaults: Defaults = defaults

    @property
    def _default_mapping(self) -> PortAppConfig | None:
        return self._defaults.port_app_config

    async def _setup(self) -> None:
        """Initialize integration with resources created by Default."""

        if not self.integration_config.initialize_port_resources:
            logger.info("Resources initialization disabled, skipping resource creation")
            return

        try:
            logger.info("Found default resources, starting creation process")
            await self._create_resources(self._defaults)
        except AbortDefaultCreationError as e:
            logger.warning(
                f"Failed to create resources. Rolling back blueprints : {e.blueprints_to_rollback}"
            )
            await asyncio.gather(
                *(
                    self.port_client.delete_blueprint(
                        identifier,
                        should_raise=False,
                        user_agent_type=UserAgentType.exporter,
                    )
                    for identifier in e.blueprints_to_rollback
                )
            )
            raise ExceptionGroup[Exception](str(e), e.errors)

    async def _create_resources(self, defaults: Defaults) -> None:
        """Create blueprints, actions, scorecards, and pages."""
        creation_stage, *blueprint_patches = (
            self._deconstruct_blueprints_to_creation_steps(defaults.blueprints)
        )

        blueprints_results, _ = await gather_and_split_errors_from_results(
            [
                self.port_client.get_blueprint(
                    blueprint["identifier"], should_log=False
                )
                for blueprint in creation_stage
            ],
            lambda item: isinstance(item, Blueprint),
        )

        mapped_blueprints_exist = await self._mapped_blueprints_exist()

        if blueprints_results or mapped_blueprints_exist:
            logger.info(
                f"Blueprints already exist: {[result.identifier for result in blueprints_results]}. Skipping integration default creation..."
            )
            return

        created_blueprints, blueprint_errors = (
            await gather_and_split_errors_from_results(
                (
                    self.port_client.create_blueprint(
                        blueprint, user_agent_type=UserAgentType.exporter
                    )
                    for blueprint in creation_stage
                )
            )
        )

        created_blueprints_identifiers = [bp["identifier"] for bp in created_blueprints]

        if blueprint_errors:
            for error in blueprint_errors:
                if isinstance(error, httpx.HTTPStatusError):
                    logger.warning(
                        f"Failed to create resources: {error.response.text}. Rolling back changes..."
                    )

            raise AbortDefaultCreationError(
                created_blueprints_identifiers, blueprint_errors
            )

        try:
            for patch_stage in blueprint_patches:
                await asyncio.gather(
                    *(
                        self.port_client.patch_blueprint(
                            blueprint["identifier"],
                            blueprint,
                            user_agent_type=UserAgentType.exporter,
                        )
                        for blueprint in patch_stage
                    )
                )

        except httpx.HTTPStatusError as err:
            logger.error(
                f"Failed to create resources: {err.response.text}. continuing..."
            )
            raise AbortDefaultCreationError(created_blueprints_identifiers, [err])

        try:
            _, actions_errors = await gather_and_split_errors_from_results(
                (
                    self.port_client.create_action(action, should_log=False)
                    for action in defaults.actions
                )
            )

            _, scorecards_errors = await gather_and_split_errors_from_results(
                (
                    self.port_client.create_scorecard(
                        blueprint_scorecards["blueprint"], action, should_log=False
                    )
                    for blueprint_scorecards in defaults.scorecards
                    for action in blueprint_scorecards["data"]
                )
            )

            _, pages_errors = await gather_and_split_errors_from_results(
                (
                    self.port_client.create_page(page, should_log=False)
                    for page in defaults.pages
                )
            )

            errors = actions_errors + scorecards_errors + pages_errors
            if errors:
                for error in errors:
                    if isinstance(error, httpx.HTTPStatusError):
                        logger.warning(
                            f"Failed to create resource: {error.response.text}. continuing..."
                        )

        except Exception as err:
            logger.error(f"Failed to create resources: {err}. continuing...")

    async def _mapped_blueprints_exist(self) -> bool:
        """Check if blueprints mapped in the integration already exist."""
        integration = await self.port_client.get_current_integration(
            should_log=False,
            should_raise=False,
        )
        integration_config = integration.get("config", {})
        resources = integration_config.get("resources", [])

        if not isinstance(resources, list):
            return True

        mapped_blueprints = []
        for resource in resources:
            blueprint = (
                resource.get("port", {})
                .get("entity", {})
                .get("mappings", {})
                .get("blueprint")
            )
            if blueprint:
                if (
                    isinstance(blueprint, str)
                    and blueprint.startswith('"')
                    and blueprint.endswith('"')
                ):
                    blueprint = blueprint.strip('"')
                mapped_blueprints.append({"identifier": blueprint})

        if not mapped_blueprints:
            return True

        existing_blueprints, _ = await gather_and_split_errors_from_results(
            [
                self.port_client.get_blueprint(
                    blueprint["identifier"], should_log=False
                )
                for blueprint in mapped_blueprints
            ],
            lambda item: isinstance(item, Blueprint),
        )

        if len(existing_blueprints) != len(mapped_blueprints):
            return False

        return True

    @staticmethod
    def _deconstruct_blueprints_to_creation_steps(
        raw_blueprints: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], ...]:
        """Deconstruct blueprints into creation stages to avoid conflicts."""
        bare_blueprint, with_relations, full_blueprint = [], [], []

        for blueprint in raw_blueprints:
            full_blueprint.append(blueprint.copy())

            blueprint.pop("calculationProperties", {})
            blueprint.pop("mirrorProperties", {})
            blueprint.pop("aggregationProperties", {})
            with_relations.append(blueprint.copy())
            blueprint.pop("teamInheritance", {})
            blueprint.pop("ownership", {})
            blueprint.pop("relations", {})
            bare_blueprint.append(blueprint)

        return (
            bare_blueprint,
            with_relations,
            full_blueprint,
        )
