"""Base initialization setup class."""

from abc import ABC, abstractmethod
from typing import Type

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
        has_provision_feature_flag: bool = False,
    ):
        self.port_client = port_client
        self.integration_config = integration_config
        self.has_provision_feature_flag = has_provision_feature_flag

    @abstractmethod
    async def initialize(self, config_class: Type[PortAppConfig]) -> None:
        """Execute initialization for this setup strategy."""
        pass

    async def _initialize_required_integration_settings(
        self,
        default_mapping: PortAppConfig | None = None,
    ) -> None:
        """Initialize integration settings at Port."""
        try:
            logger.info("Initializing integration at port")
            integration = await self.port_client.get_current_integration(
                should_log=False,
                should_raise=False,
                has_provision_feature_flag=self.has_provision_feature_flag,
            )
            if not integration:
                logger.info(
                    "Integration does not exist, Creating new integration with default mapping"
                )
                integration = await self.port_client.create_integration(
                    self.integration_config.integration.type,
                    self.integration_config.event_listener.get_changelog_destination_details(),
                    port_app_config=default_mapping,
                    actions_processing_enabled=self.integration_config.actions_processor.enabled,
                    create_port_resources_origin_in_port=self._should_create_resources_in_port(),
                )
            elif not integration.get("config", None):
                logger.info(
                    "Encountered that the integration's mapping is empty, Initializing to default mapping"
                )
                integration = await self.port_client.patch_integration(
                    self.integration_config.integration.type,
                    self.integration_config.event_listener.get_changelog_destination_details(),
                    port_app_config=default_mapping,
                )
        except httpx.HTTPStatusError as err:
            logger.error(f"Failed to apply default mapping: {err.response.text}.")
            raise err

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

    def _should_create_resources_in_port(self) -> bool:
        """Check if resources should be created in Port."""
        return (
            self.integration_config.create_port_resources_origin
            == CreatePortResourcesOrigin.Port
        )
