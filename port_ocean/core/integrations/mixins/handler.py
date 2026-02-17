from typing import Type

from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.core.handlers import (
    BaseEntityProcessor,
    BasePortAppConfig,
    BaseEntitiesStateApplier,
    HttpEntitiesStateApplier,
    JQEntityProcessor,
    APIPortAppConfig,
)
from port_ocean.exceptions.core import IntegrationNotStartedException


class HandlerMixin:
    """Mixin class for handling integration components.

    This mixin class provides methods and properties for initializing and accessing various
    integration components, including the Entity Processor, PortAppConfig Handler, and
    EntitiesStateApplier.

    Attributes:
        EntityProcessorClass (Type[BaseEntityProcessor]): The class representing the Entity Processor.
        AppConfigHandlerClass (Type[BasePortAppConfig]): The class representing the PortAppConfig Handler.
        EntitiesStateApplierClass (Type[BaseEntitiesStateApplier]): The class representing the EntitiesStateApplier.
    """

    EntityProcessorClass: Type[BaseEntityProcessor] = JQEntityProcessor

    AppConfigHandlerClass: Type[BasePortAppConfig] = APIPortAppConfig

    EntitiesStateApplierClass: Type[BaseEntitiesStateApplier] = HttpEntitiesStateApplier

    def __init__(self) -> None:
        self._entity_processor: BaseEntityProcessor | None = None
        self._port_app_config_handler: BasePortAppConfig | None = None
        self._entities_state_applier: BaseEntitiesStateApplier | None = None

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

    async def initialize_handlers(self) -> None:
        """Initialize all integration components."""
        logger.info("Initializing integration components")
        await self._init_entity_processor_instance()
        await self._init_port_app_config_handler_instance()
        await self._init_entities_state_applier_instance()
