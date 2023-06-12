from abc import abstractmethod
from logging import Logger
from typing import (
    List,
    Callable,
    Awaitable,
    TypedDict,
    NoReturn,
    Dict,
)

from port_ocean.context.event import EventContext, initialize_event_context
from port_ocean.context.integration import PortOceanContext
from port_ocean.core.handlers import (
    BaseManipulation,
    BasePortAppConfigHandler,
    BaseTransport,
    JQManipulation,
    HttpPortAppConfig,
    HttpPortTransport,
)
from port_ocean.models.diff import Change
from port_ocean.models.port_app_config import ResourceConfig

RESYNC_EVENT_LISTENER = Callable[[str], Awaitable[Change]]
START_EVENT_LISTENER = Callable[[], Awaitable]


class EventsCallbacks(TypedDict):
    start: List[START_EVENT_LISTENER]
    resync: List[RESYNC_EVENT_LISTENER]


class BaseIntegration:
    ManipulationHandlerClass: Callable[
        [PortOceanContext, Logger], BaseManipulation
    ] = JQManipulation

    AppConfigHandlerClass: Callable[
        [PortOceanContext, Logger], BasePortAppConfigHandler
    ] = HttpPortAppConfig

    TransportHandlerClass: Callable[
        [PortOceanContext, Logger], BaseTransport
    ] = HttpPortTransport

    def __init__(self, context: PortOceanContext, logger: Logger):
        self._manipulation: BaseManipulation | None = None
        self._port_app_config: BasePortAppConfigHandler | None = None
        self._transport: BaseTransport | None = None
        self.logger = logger

        self.started = False
        self.context = context
        self.event_strategy: EventsCallbacks = {
            "start": [],
            "resync": [],
        }
        # self.trigger_channel = TriggerChannelFactory(
        #     self.context.config.integration.identifier,
        #     self.context.config.trigger_channel.type,
        #     {"action": self.trigger_action, "resync": self.trigger_resync},
        # )

    @property
    def manipulation(self) -> BaseManipulation:
        if not self._manipulation:
            raise Exception("Integration not started")
        return self._manipulation

    @property
    def port_app_config(self) -> BasePortAppConfigHandler:
        if self._port_app_config is None:
            raise Exception("Integration not started")
        return self._port_app_config

    @property
    def port_client(self) -> BaseTransport:
        if not self._transport:
            raise Exception("Integration not started")
        return self._transport

    async def _init_manipulation_instance(self) -> BaseManipulation:
        self._manipulation = self.ManipulationHandlerClass(self.context, self.logger)
        return self._manipulation

    async def _init_port_app_config_handler_instance(self) -> BasePortAppConfigHandler:
        self._port_app_config = self.AppConfigHandlerClass(self.context, self.logger)
        return self._port_app_config

    async def _init_transport_instance(self) -> BaseTransport:
        self._transport = self.TransportHandlerClass(self.context, self.logger)
        return self._transport

    @abstractmethod
    async def _on_resync(self, kind: str) -> Change:
        pass

    def on_start(self, func: START_EVENT_LISTENER) -> START_EVENT_LISTENER:
        self.event_strategy["start"].append(func)
        return func

    def on_resync(self, func: RESYNC_EVENT_LISTENER) -> RESYNC_EVENT_LISTENER:
        self.event_strategy["resync"].append(func)
        return func

    async def _register_raw(
        self, raw_diff: Dict[ResourceConfig, List[Change]]
    ) -> NoReturn:
        parsed_entities = [
            self.manipulation.get_diff(mapping, results)
            for mapping, results in raw_diff.items()
        ]
        await self.port_client.update_diff(parsed_entities)

    async def register_state(self, kind: str, entities_state: Change) -> NoReturn:
        config = await self.port_app_config.get_port_app_config()
        resource_mappings = [
            resource for resource in config.resources if resource.kind == kind
        ]

        await self._register_raw(
            {mapping: [entities_state] for mapping in resource_mappings}
        )

    async def trigger_start(self) -> None:
        if self.started:
            raise Exception("Integration already started")

        if (
            not self.event_strategy["resync"]
            and self.__class__._on_resync == BaseIntegration._on_resync
        ):
            raise NotImplementedError("on_resync is not implemented")

        await self._init_manipulation_instance()
        await self._init_port_app_config_handler_instance()
        await self._init_transport_instance()
        # self.trigger_channel.create_trigger_channel()

        # ocean.port_client.initiate_integration(
        #     self.config.integration.identifier,
        #     self.config.integration.type,
        #     self.config.trigger_channel.type,
        # )

        self.started = True
        initialize_event_context(EventContext("start"))

        for listener in self.event_strategy["start"]:
            await listener()

    async def trigger_action(self, action: str) -> NoReturn:
        raise NotImplementedError("trigger_action is not implemented")

    async def trigger_resync(self) -> NoReturn:
        app_config = await self.port_app_config.get_port_app_config()
        results = []
        mapping_object_to_raw_data = {}

        for resource in app_config.resources:
            initialize_event_context(EventContext("rsync", resource, app_config))

            if self.__class__._on_resync != BaseIntegration._on_resync:
                results.append(await self._on_resync(resource.kind))

            for wrapper in self.event_strategy["resync"]:
                results.append(await wrapper(resource.kind))

            mapping_object_to_raw_data[resource] = results

        await self._register_raw(mapping_object_to_raw_data)
