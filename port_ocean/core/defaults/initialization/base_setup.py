from abc import ABC, abstractmethod
from typing import Any, Type

from loguru import logger

from port_ocean.clients.port.client import PortClient
from port_ocean.config.settings import IntegrationConfiguration
from port_ocean.core.handlers.port_app_config.models import PortAppConfig


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
    @abstractmethod
    def _default_mapping(self) -> PortAppConfig | None:
        pass

    @abstractmethod
    async def _setup(self) -> None:
        pass

    async def setup(self, integration: dict[str, Any]) -> None:
        """Execute initialization for this setup strategy."""

        if integration.get("arePortResourcesInitialized", False):
            logger.info("Port resources are already initialized, skipping setup")
            return

        logger.info("Initializing integration at port")
        await self._setup()
