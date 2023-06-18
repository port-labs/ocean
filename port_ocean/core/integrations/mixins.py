from typing import Callable

from port_ocean.context.integration import PortOceanContext, ocean
from port_ocean.core.handlers import (
    BaseManipulation,
    BasePortAppConfigWithContext,
    BaseTransport,
)
from port_ocean.core.handlers.manipulation.jq_manipulation import JQManipulation
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.transport.port.transport import HttpPortTransport
from port_ocean.types import (
    START_EVENT_LISTENER,
    RESYNC_EVENT_LISTENER,
    IntegrationEventsCallbacks,
)


class EventsMixin:
    def __init__(self) -> None:
        self.event_strategy: IntegrationEventsCallbacks = {
            "start": [],
            "resync": [],
        }

    def on_start(self, func: START_EVENT_LISTENER) -> START_EVENT_LISTENER:
        self.event_strategy["start"].append(func)
        return func

    def on_resync(self, func: RESYNC_EVENT_LISTENER) -> RESYNC_EVENT_LISTENER:
        self.event_strategy["resync"].append(func)
        return func


class HandlerMixin:
    ManipulationHandlerClass: Callable[
        [PortOceanContext], BaseManipulation
    ] = JQManipulation

    AppConfigHandlerClass: Callable[
        [PortOceanContext], BasePortAppConfigWithContext
    ] = APIPortAppConfig

    TransportHandlerClass: Callable[
        [PortOceanContext], BaseTransport
    ] = HttpPortTransport

    def __init__(self) -> None:
        self._manipulation: BaseManipulation | None = None
        self._port_app_config: BasePortAppConfigWithContext | None = None
        self._transport: BaseTransport | None = None

    @property
    def manipulation(self) -> BaseManipulation:
        if not self._manipulation:
            raise Exception("Integration not started")
        return self._manipulation

    @property
    def port_app_config(self) -> BasePortAppConfigWithContext:
        if self._port_app_config is None:
            raise Exception("Integration not started")
        return self._port_app_config

    @property
    def port_client(self) -> BaseTransport:
        if not self._transport:
            raise Exception("Integration not started")
        return self._transport

    async def _init_manipulation_instance(self) -> BaseManipulation:
        self._manipulation = self.ManipulationHandlerClass(ocean)
        return self._manipulation

    async def _init_port_app_config_handler_instance(
        self,
    ) -> BasePortAppConfigWithContext:
        self._port_app_config = self.AppConfigHandlerClass(ocean)
        return self._port_app_config

    async def _init_transport_instance(self) -> BaseTransport:
        self._transport = self.TransportHandlerClass(ocean)
        return self._transport
