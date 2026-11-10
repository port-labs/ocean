from typing import Type

from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.core.handlers import (
    BaseEntityProcessor,
    BasePortAppConfig,
    BaseEntitiesStateApplier,
    BaseRawEnricher,
    HttpEntitiesStateApplier,
    JQEntityProcessor,
    APIPortAppConfig,
)
from port_ocean.exceptions.core import IntegrationNotStartedException


class HandlerMixin:
    """Mixin class for handling integration components.

    This mixin class provides methods and properties for initializing and accessing various
    integration components, including the Entity Processor, PortAppConfig Handler,
    EntitiesStateApplier and Raw Enricher.

    Attributes:
        EntityProcessorClass (Type[BaseEntityProcessor]): The class representing the Entity Processor.
        AppConfigHandlerClass (Type[BasePortAppConfig]): The class representing the PortAppConfig Handler.
        EntitiesStateApplierClass (Type[BaseEntitiesStateApplier]): The class representing the EntitiesStateApplier.
        RawEnricherClass (Type[BaseRawEnricher]): The class that attaches data a mapping needs
            to raw items before they are sent to the data-source-processor (e.g. the contents
            behind the deprecated `file://` / `search://` mapping values).
    """

    EntityProcessorClass: Type[BaseEntityProcessor] = JQEntityProcessor

    AppConfigHandlerClass: Type[BasePortAppConfig] = APIPortAppConfig

    EntitiesStateApplierClass: Type[BaseEntitiesStateApplier] = HttpEntitiesStateApplier

    RawEnricherClass: Type[BaseRawEnricher] = BaseRawEnricher

    def __init__(self) -> None:
        self._entity_processor: BaseEntityProcessor | None = None
        self._port_app_config_handler: BasePortAppConfig | None = None
        self._entities_state_applier: BaseEntitiesStateApplier | None = None
        self._raw_enricher: BaseRawEnricher | None = None

    @property
    def entity_processor(self) -> BaseEntityProcessor:
        """Access the Entity Processor instance.

        Raises:
            IntegrationNotStartedException: If the Entity Processor class is not initialized.
        """
        if not self._entity_processor:
            raise IntegrationNotStartedException(
                "Entity Processor class not initialized"
            )
        return self._entity_processor

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
    def entities_state_applier(self) -> BaseEntitiesStateApplier:
        """Access the EntitiesStateApplier instance.

        Raises:
            IntegrationNotStartedException: If the EntitiesStateApplier class is not initialized.
        """
        if not self._entities_state_applier:
            raise IntegrationNotStartedException(
                "EntitiesStateApplier class not initialized"
            )
        return self._entities_state_applier

    @property
    def raw_enricher(self) -> BaseRawEnricher:
        """Access the Raw Enricher instance.

        Raises:
            IntegrationNotStartedException: If the Raw Enricher class is not initialized.
        """
        if self._raw_enricher is None:
            raise IntegrationNotStartedException("RawEnricher class not initialized")
        return self._raw_enricher

    async def _init_entity_processor_instance(self) -> BaseEntityProcessor:
        self._entity_processor = self.EntityProcessorClass(ocean)
        return self._entity_processor

    async def _init_port_app_config_handler_instance(
        self,
    ) -> BasePortAppConfig:
        self._port_app_config_handler = self.AppConfigHandlerClass(ocean)
        return self._port_app_config_handler

    async def _init_entities_state_applier_instance(self) -> BaseEntitiesStateApplier:
        self._entities_state_applier = self.EntitiesStateApplierClass(ocean)
        return self._entities_state_applier

    async def _init_raw_enricher_instance(self) -> BaseRawEnricher:
        self._raw_enricher = self.RawEnricherClass(ocean)
        return self._raw_enricher

    async def initialize_handlers(self) -> None:
        """Initialize all integration components."""
        logger.info("Initializing integration components")
        await self._init_entity_processor_instance()
        await self._init_port_app_config_handler_instance()
        await self._init_entities_state_applier_instance()
        await self._init_raw_enricher_instance()
