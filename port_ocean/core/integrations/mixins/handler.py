from typing import Callable

from loguru import logger

from port_ocean.context.ocean import PortOceanContext, ocean
from port_ocean.core.handlers import (
    BaseManipulation,
    BasePortAppConfig,
    BaseEntitiesStateApplier,
)
from port_ocean.core.handlers.entities_state_applier.port.applier import (
    HttpEntitiesStateApplier,
)
from port_ocean.core.handlers.manipulation.jq_manipulation import JQManipulation
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.exceptions.core import IntegrationNotStartedException


class HandlerMixin:
    ManipulationHandlerClass: Callable[
        [PortOceanContext], BaseManipulation
    ] = JQManipulation

    AppConfigHandlerClass: Callable[
        [PortOceanContext], BasePortAppConfig
    ] = APIPortAppConfig

    EntitiesStateApplierClass: Callable[
        [PortOceanContext], BaseEntitiesStateApplier
    ] = HttpEntitiesStateApplier

    def __init__(self) -> None:
        self._manipulation: BaseManipulation | None = None
        self._port_app_config_handler: BasePortAppConfig | None = None
        self._entities_state_applier: BaseEntitiesStateApplier | None = None

    @property
    def manipulation(self) -> BaseManipulation:
        if not self._manipulation:
            raise IntegrationNotStartedException("Manipulation class not initialized")
        return self._manipulation

    @property
    def port_app_config_handler(self) -> BasePortAppConfig:
        if self._port_app_config_handler is None:
            raise IntegrationNotStartedException("PortAppConfig class not initialized")
        return self._port_app_config_handler

    @property
    def entities_state_applier(self) -> BaseEntitiesStateApplier:
        if not self._entities_state_applier:
            raise IntegrationNotStartedException(
                "EntitiesStateApplier class not initialized"
            )
        return self._entities_state_applier

    async def _init_manipulation_instance(self) -> BaseManipulation:
        self._manipulation = self.ManipulationHandlerClass(ocean)
        return self._manipulation

    async def _init_port_app_config_handler_instance(
        self,
    ) -> BasePortAppConfig:
        self._port_app_config_handler = self.AppConfigHandlerClass(ocean)
        return self._port_app_config_handler

    async def _init_entities_state_applier_instance(self) -> BaseEntitiesStateApplier:
        self._entities_state_applier = self.EntitiesStateApplierClass(ocean)
        return self._entities_state_applier

    async def initialize_handlers(self) -> None:
        logger.info("Initializing integration components")
        await self._init_manipulation_instance()
        await self._init_port_app_config_handler_instance()
        await self._init_entities_state_applier_instance()
