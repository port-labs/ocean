from abc import abstractmethod
from typing import (
    List,
    Callable,
    Awaitable,
    TypedDict,
    NoReturn,
)

from port_ocean.config.integration import IntegrationConfiguration
from port_ocean.context.event import EventContext, initialize_event_context
from port_ocean.core.manipulation.base import BaseManipulation
from port_ocean.core.manipulation.jq_manipulation import JQManipulation
from port_ocean.core.port.base import BasePortClient
from port_ocean.core.port.port import PortClient
from port_ocean.core.port_app_config.base import BasePortAppConfigHandler
from port_ocean.models.diff import Change

# from port_ocean.core.trigger_channel.trigger_channel_factory import TriggerChannelFactory


RESYNC_EVENT_LISTENER = Callable[[str], Awaitable[Change]]
START_EVENT_LISTENER = Callable[[], Awaitable]


class EventsCallbacks(TypedDict):
    start: List[START_EVENT_LISTENER]
    resync: List[RESYNC_EVENT_LISTENER]


class BaseIntegration:
    ManipulationClass: Callable[
        [IntegrationConfiguration], BaseManipulation
    ] = JQManipulation

    AppConfigClass: Callable[
        [IntegrationConfiguration], BasePortAppConfigHandler
    ] = BasePortAppConfigHandler

    PortClientClass: Callable[[IntegrationConfiguration], BasePortClient] = PortClient

    def __init__(self, config: IntegrationConfiguration):
        self._manipulation: BaseManipulation | None = None
        self._port_app_config: BasePortAppConfigHandler | None = None
        self._port_client: BasePortClient | None = None

        self.started = False
        self.config = config
        self.event_strategy: EventsCallbacks = {
            "start": [],
            "resync": [],
        }
        # self.trigger_channel = TriggerChannelFactory(self.config.trigger_channel.type).create_trigger_channel(
        #     self.on_action,
        #     self.trigger_resync
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
    def port_client(self) -> BasePortClient:
        if not self._port_client:
            raise Exception("Integration not started")
        return self._port_client

    async def _init_manipulation_instance(self) -> BaseManipulation:
        self._manipulation = self.ManipulationClass(self.config)
        return self._manipulation

    async def _init_port_configuration_instance(self) -> BasePortAppConfigHandler:
        self._port_app_config = self.AppConfigClass(self.config)
        return self._port_app_config

    async def _init_port_client_instance(self) -> BasePortClient:
        self._port_client = self.PortClientClass(self.config)
        return self._port_client

    @abstractmethod
    async def _on_resync(self, kind: str) -> Change:
        pass

    def on_start(self, func: START_EVENT_LISTENER) -> START_EVENT_LISTENER:
        self.event_strategy["start"].append(func)
        return func

    def on_resync(self, func: RESYNC_EVENT_LISTENER) -> RESYNC_EVENT_LISTENER:
        self.event_strategy["resync"].append(func)
        return func

    async def register_state(self, kind: str, entities_state: Change) -> NoReturn:
        config = await self.port_app_config.get_port_app_config()
        resource_mappings = [
            resource for resource in config.resources if resource.kind == kind
        ]

        parsed_entities = [
            self.manipulation.get_diff(mapping, [entities_state])
            for mapping in resource_mappings
        ]
        await self.port_client.register(parsed_entities)

    async def trigger_start(self) -> None:
        if self.started:
            raise Exception("Integration already started")

        if (
            not self.event_strategy["resync"]
            and self.__class__._on_resync == BaseIntegration._on_resync
        ):
            raise NotImplementedError("on_resync is not implemented")

        await self._init_manipulation_instance()
        await self._init_port_configuration_instance()
        # port_client = await self._init_port_client_instance()
        #
        # port_client.initiate_integration(
        #     self.config.integration.identifier,
        #     self.config.integration.type,
        #     self.config.trigger_channel,
        # )

        self.started = True
        initialize_event_context(EventContext("start"))

        for listener in self.event_strategy["start"]:
            await listener()

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

        parsed_entities = [
            self.manipulation.get_diff(mappings, results)
            for mappings, results in mapping_object_to_raw_data.items()
        ]
        await self.port_client.register(parsed_entities)
