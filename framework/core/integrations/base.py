from abc import abstractmethod
from typing import List, Callable, Awaitable, TypedDict, Type

from framework.config.integration import IntegrationConfiguration
from framework.context.event import EventContext, initialize_event_context
from framework.core.manipulation.base import BaseManipulation
from framework.core.manipulation.jq_manipulation import JQManipulation
from framework.port.port import PortClient


# from framework.core.trigger_channel.trigger_channel_factory import TriggerChannelFactory


class Change(TypedDict):
    before: List[dict]
    after: List[dict]


RESYNC_EVENT_LISTENER = Callable[[str], Awaitable[Change]]


class EventsCallbacks(TypedDict):
    start: List[Callable[[], Awaitable]]
    resync: List[RESYNC_EVENT_LISTENER]


class BaseIntegration:
    ManipulationClass: Type[BaseManipulation] = JQManipulation
    TransportClass = None
    AppConfigClass = None
    PortClientClass: Type[PortClient] = PortClient

    def __init__(self, config: IntegrationConfiguration):
        (
            self._manipulation,
            self._transport,
            self._port_app_config,
            self._port_client,
        ) = (None, None, None, None)
        self.started = False
        self.config = config
        self.event_strategy: EventsCallbacks = {"start": [], "resync": []}
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
    def transport(self):
        if not self._transport:
            raise Exception("Integration not started")
        return self._transport

    @property
    def port_app_config(self):
        if not self._port_app_config:
            raise Exception("Integration not started")
        return self._port_app_config

    @property
    def port_client(self) -> PortClient:
        if not self._port_client:
            raise Exception("Integration not started")
        return self._port_client

    async def _init_manipulation_instance(self):
        self._manipulation = self.ManipulationClass()
        return self._manipulation

    async def _init_transport_instance(self):
        self._transport = self.TransportClass()
        return self._transport

    async def _init_port_configuration_instance(self):
        self._port_app_config = self.AppConfigClass()
        return self._port_app_config

    async def _init_port_client_instance(self):
        self._port_client = self.PortClientClass(
            self.config.port.client_id,
            self.config.port.client_secret,
            self.config.port.base_url,
            self.config.integration.identifier,
        )
        return self._port_client

    @abstractmethod
    async def _on_resync(self, kind: str) -> Change:
        pass

    def on_start(self, func: Callable):
        self.event_strategy["start"].append(func)
        return func

    def on_resync(self, func: RESYNC_EVENT_LISTENER):
        self.event_strategy["resync"].append(func)
        return func

    async def register_state(self, kind: str, entities_state: Change):
        resource_mappings = [
            resource
            for resource in self.port_app_config.resources
            if resource.kind == kind
        ]

        parsed_entities = [
            self.manipulation.get_entities_diff(mapping, [entities_state])
            for mapping in resource_mappings
        ]
        await self.transport.send(parsed_entities)

    async def trigger_start(self):
        if self.started:
            raise Exception("Integration already started")

        if (
            not self.event_strategy["resync"]
            and self.__class__._on_resync == BaseIntegration._on_resync
        ):
            raise NotImplementedError("on_resync is not implemented")

        await self._init_manipulation_instance()
        await self._init_transport_instance()
        await self._init_port_configuration_instance()
        port_client = await self._init_port_client_instance()

        port_client.initiate_integration(
            self.config.integration.identifier,
            self.config.integration.type,
            self.config.trigger_channel,
        )

        self.started = True
        initialize_event_context(EventContext("start"))

        for listener in self.event_strategy["start"]:
            await listener()

    async def trigger_resync(self):
        app_config = await self._init_port_configuration_instance()
        results = []
        mapping_object_to_raw_data = {}

        for resource in app_config.resources:
            initialize_event_context(EventContext("rsync", resource, app_config))

            if self.__class__._on_resync != BaseIntegration._on_resync:
                results.append(await self._on_resync(resource))

            for wrapper in self.event_strategy["resync"]:
                results.append(await wrapper(resource))

            mapping_object_to_raw_data[resource] = results

        parsed_entities = [
            self.manipulation.get_entities_diff(mappings, results)
            for mappings, results in mapping_object_to_raw_data.items()
        ]
        await self.transport.send(parsed_entities)
