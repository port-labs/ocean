from typing import Callable

from loguru import logger
from port_ocean.context.ocean import PortOceanContext, ocean
from port_ocean.core.handlers import BaseManipulation, BasePortAppConfig, BaseTransport
from port_ocean.core.handlers.manipulation.jq_manipulation import JQManipulation
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.transport.port.transport import HttpPortTransport
from port_ocean.exceptions.base import IntegrationNotStartedException


class HandlerMixin:
    ManipulationHandlerClass: Callable[
        [PortOceanContext], BaseManipulation
    ] = JQManipulation

    AppConfigHandlerClass: Callable[
        [PortOceanContext], BasePortAppConfig
    ] = APIPortAppConfig

    TransportHandlerClass: Callable[
        [PortOceanContext], BaseTransport
    ] = HttpPortTransport

    def __init__(self) -> None:
        self._manipulation: BaseManipulation | None = None
        self._port_app_config_handler: BasePortAppConfig | None = None
        self._transport: BaseTransport | None = None

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
    def transport(self) -> BaseTransport:
        if not self._transport:
            raise IntegrationNotStartedException("Transport class not initialized")
        return self._transport

    async def _init_manipulation_instance(self) -> BaseManipulation:
        self._manipulation = self.ManipulationHandlerClass(ocean)
        return self._manipulation

    async def _init_port_app_config_handler_instance(
        self,
    ) -> BasePortAppConfig:
        self._port_app_config_handler = self.AppConfigHandlerClass(ocean)
        return self._port_app_config_handler

    async def _init_transport_instance(self) -> BaseTransport:
        self._transport = self.TransportHandlerClass(ocean)
        return self._transport

    async def initialize_handlers(self) -> None:
        logger.info("Initializing integration components")
        await self._init_manipulation_instance()
        await self._init_port_app_config_handler_instance()
        await self._init_transport_instance()
