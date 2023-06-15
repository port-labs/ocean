from abc import abstractmethod
from typing import (
    List,
    Callable,
    Dict,
    Any,
)

from port_ocean.context.event import EventContext, initialize_event_context
from port_ocean.context.integration import PortOceanContext
from port_ocean.core.handlers import (
    BaseManipulation,
    BasePortAppConfigWithContext,
    BaseTransport,
    JQManipulation,
    HttpPortAppConfig,
    HttpPortTransport,
)
from port_ocean.core.trigger_channel.trigger_channel_factory import (
    TriggerChannelFactory,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.types import (
    START_EVENT_LISTENER,
    RESYNC_EVENT_LISTENER,
    ObjectDiff,
    IntegrationEventsCallbacks,
)


class BaseIntegration:
    ManipulationHandlerClass: Callable[
        [PortOceanContext], BaseManipulation
    ] = JQManipulation

    AppConfigHandlerClass: Callable[
        [PortOceanContext], BasePortAppConfigWithContext
    ] = HttpPortAppConfig

    TransportHandlerClass: Callable[
        [PortOceanContext], BaseTransport
    ] = HttpPortTransport

    def __init__(self, context: PortOceanContext):
        self._manipulation: BaseManipulation | None = None
        self._port_app_config: BasePortAppConfigWithContext | None = None
        self._transport: BaseTransport | None = None

        self.started = False
        self.context = context
        self.event_strategy: IntegrationEventsCallbacks = {
            "start": [],
            "resync": [],
        }
        self.trigger_channel = TriggerChannelFactory(
            context,
            self.context.config.integration.identifier,
            self.context.config.trigger_channel.type,
            {"on_action": self.trigger_action, "on_resync": self.trigger_resync},
        )

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
        self._manipulation = self.ManipulationHandlerClass(self.context)
        return self._manipulation

    async def _init_port_app_config_handler_instance(
        self,
    ) -> BasePortAppConfigWithContext:
        self._port_app_config = self.AppConfigHandlerClass(self.context)
        return self._port_app_config

    async def _init_transport_instance(self) -> BaseTransport:
        self._transport = self.TransportHandlerClass(self.context)
        return self._transport

    @abstractmethod
    async def _on_resync(self, kind: str) -> ObjectDiff:
        pass

    def on_start(self, func: START_EVENT_LISTENER) -> START_EVENT_LISTENER:
        self.event_strategy["start"].append(func)
        return func

    def on_resync(self, func: RESYNC_EVENT_LISTENER) -> RESYNC_EVENT_LISTENER:
        self.event_strategy["resync"].append(func)
        return func

    async def _register_raw(
        self, raw_diff: Dict[ResourceConfig, List[ObjectDiff]]
    ) -> None:
        parsed_entities = [
            self.manipulation.get_diff(mapping, results)
            for mapping, results in raw_diff.items()
        ]
        await self.port_client.update_diff(parsed_entities)

    async def register_state(self, kind: str, entities_state: ObjectDiff) -> None:
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

    async def trigger_action(self, data: Dict[Any, Any]) -> None:
        raise NotImplementedError("trigger_action is not implemented")

    async def trigger_resync(self, _: Dict[Any, Any] | None = None) -> None:
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
