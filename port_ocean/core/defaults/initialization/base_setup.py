from abc import ABC, abstractmethod
from typing import Any, Type

import httpx
from loguru import logger

from port_ocean.clients.port.client import PortClient
from port_ocean.config.settings import IntegrationConfiguration
from port_ocean.core.handlers.port_app_config.models import PortAppConfig
from port_ocean.core.models import CreatePortResourcesOrigin


class BaseSetup(ABC):
    """Abstract base class for initialization setup strategies."""

    def __init__(
        self,
        port_client: PortClient,
        integration_config: IntegrationConfiguration,
        config_class: Type[PortAppConfig],
    ):
        self.port_client = port_client
        self.integration_config = integration_config
        self.config_class = config_class

    @property
    def _is_port_provisioning_enabled(self) -> bool:
        return False

    @property
    @abstractmethod
    def _port_resources_origin(self) -> CreatePortResourcesOrigin:
        pass

    @property
    @abstractmethod
    def _default_mapping(self) -> PortAppConfig | None:
        pass

    @abstractmethod
    async def _setup(self) -> None:
        pass

    async def _verify_integration_configuration(
        self,
        integration: dict[str, Any],
    ) -> None:
        """Verify integration configuration and update if necessary."""
        logger.info("Checking for diff in integration configuration")
        changelog_destination = (
            self.integration_config.event_listener.get_changelog_destination_details()
        )
        if (
            integration.get("changelogDestination") != changelog_destination
            or integration.get("installationAppType")
            != self.integration_config.integration.type
            or integration.get("version") != self.port_client.integration_version
            or integration.get("actionsProcessingEnabled")
            != self.integration_config.actions_processor.enabled
        ):
            await self.port_client.patch_integration(
                _type=self.integration_config.integration.type,
                changelog_destination=changelog_destination,
                actions_processing_enabled=self.integration_config.actions_processor.enabled,
            )

    async def _upsert_integration(self) -> dict[str, Any] | None:
        try:
            integration = await self.port_client.get_current_integration(
                should_log=False,
                should_raise=False,
            )
            if not integration:
                logger.info(
                    "Integration does not exist, Creating new integration with default mapping"
                )
                integration = await self.port_client.create_integration(
                    self.integration_config.integration.type,
                    self.integration_config.event_listener.get_changelog_destination_details(),
                    port_app_config=self._default_mapping,
                    actions_processing_enabled=self.integration_config.actions_processor.enabled,
                    create_port_resources_origin_in_port=self._port_resources_origin,
                )

            return integration
        except httpx.HTTPStatusError as err:
            logger.error(f"Failed to verify integration state: {err.response.text}.")
            raise err

    async def setup(self) -> None:
        """Execute initialization for this setup strategy."""

        logger.info("Initializing integration at port")
        integration = await self._upsert_integration()
        if integration:
            await self._verify_integration_configuration(integration)

        await self._setup()
