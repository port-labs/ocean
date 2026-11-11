from typing import Type

from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.core.handlers import (
    APIPortAppConfig,
    BasePortAppConfig,
)
from port_ocean.exceptions.core import IntegrationNotStartedException


class HandlerMixin:
    """Mixin class for handling integration components.

    This mixin class provides methods and properties for initializing and accessing the
    PortAppConfig Handler.

    Attributes:
        AppConfigHandlerClass (Type[BasePortAppConfig]): The class representing the PortAppConfig Handler.
    """

    AppConfigHandlerClass: Type[BasePortAppConfig] = APIPortAppConfig

    def __init__(self) -> None:
        self._port_app_config_handler: BasePortAppConfig | None = None

    @property
    def port_app_config_handler(self) -> BasePortAppConfig:
        """Access the PortAppConfig Handler instance.

        Raises:
            IntegrationNotStartedException: If the PortAppConfig Handler class is not initialized.
        """
        if self._port_app_config_handler is None:
            raise IntegrationNotStartedException("PortAppConfig class not initialized")
        return self._port_app_config_handler

    async def _init_port_app_config_handler_instance(
        self,
    ) -> BasePortAppConfig:
        self._port_app_config_handler = self.AppConfigHandlerClass(ocean)
        return self._port_app_config_handler

    async def initialize_handlers(self) -> None:
        """Initialize all integration components."""
        logger.info("Initializing integration components")
        await self._init_port_app_config_handler_instance()
