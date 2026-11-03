from typing import Type

from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.core.handlers import (
    APIPortAppConfig,
    BasePortAppConfig,
    BaseRawEnricher,
)
from port_ocean.exceptions.core import IntegrationNotStartedException


class HandlerMixin:
    """Mixin class for handling integration components.

    This mixin class provides methods and properties for initializing and accessing the
    PortAppConfig Handler and the Raw Enricher.

    Attributes:
        AppConfigHandlerClass (Type[BasePortAppConfig]): The class representing the PortAppConfig Handler.
        RawEnricherClass (Type[BaseRawEnricher]): The class that attaches data a mapping needs
            (e.g. `file://` contents) to raw items before they are sent to the data-source-processor.
    """

    AppConfigHandlerClass: Type[BasePortAppConfig] = APIPortAppConfig

    RawEnricherClass: Type[BaseRawEnricher] = BaseRawEnricher

    def __init__(self) -> None:
        self._port_app_config_handler: BasePortAppConfig | None = None
        self._raw_enricher: BaseRawEnricher | None = None

    @property
    def port_app_config_handler(self) -> BasePortAppConfig:
        """Access the PortAppConfig Handler instance.

        Raises:
            IntegrationNotStartedException: If the PortAppConfig Handler class is not initialized.
        """
        if self._port_app_config_handler is None:
            raise IntegrationNotStartedException("PortAppConfig class not initialized")
        return self._port_app_config_handler

    @property
    def raw_enricher(self) -> BaseRawEnricher:
        """Access the Raw Enricher instance.

        Raises:
            IntegrationNotStartedException: If the Raw Enricher class is not initialized.
        """
        if self._raw_enricher is None:
            raise IntegrationNotStartedException("RawEnricher class not initialized")
        return self._raw_enricher

    async def _init_port_app_config_handler_instance(
        self,
    ) -> BasePortAppConfig:
        self._port_app_config_handler = self.AppConfigHandlerClass(ocean)
        return self._port_app_config_handler

    async def _init_raw_enricher_instance(self) -> BaseRawEnricher:
        self._raw_enricher = self.RawEnricherClass(ocean)
        return self._raw_enricher

    async def initialize_handlers(self) -> None:
        """Initialize all integration components."""
        logger.info("Initializing integration components")
        await self._init_port_app_config_handler_instance()
        await self._init_raw_enricher_instance()
