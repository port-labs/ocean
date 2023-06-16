import asyncio
from abc import abstractmethod
from typing import (
    List,
    Dict,
    Any,
    Tuple,
    Awaitable,
)

from loguru import logger

from port_ocean.context.event import EventContext, initialize_event_context
from port_ocean.context.integration import PortOceanContext

from port_ocean.core.integrations.mixins import HandlerMixin, EventsMixin
from port_ocean.core.trigger_channel.trigger_channel_factory import (
    TriggerChannelFactory,
)
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortAppConfig,
)
from port_ocean.core.utils import validate_result
from port_ocean.types import (
    ObjectDiff,
)


class BaseIntegration(HandlerMixin, EventsMixin):
    def __init__(self, context: PortOceanContext):
        HandlerMixin.__init__(self)
        EventsMixin.__init__(self)

        self.started = False
        self.context = context
        self.trigger_channel = TriggerChannelFactory(
            context,
            self.context.config.integration.identifier,
            self.context.config.trigger_channel.type,
            {"on_action": self.trigger_action, "on_resync": self.trigger_resync},
        )

    async def _on_resync(self, kind: str) -> ObjectDiff:
        raise NotImplementedError("on_resync must be implemented")

    async def _register_raw(
        self, raw_diff: List[Tuple[ResourceConfig, List[ObjectDiff]]]
    ) -> None:
        parsed_entities = await asyncio.gather(
            *[
                self.manipulation.get_diff(mapping, results)
                for mapping, results in raw_diff
            ]
        )

        await self.port_client.update_diff(parsed_entities)

    async def _resync_resource(
        self, resource_config: ResourceConfig, app_config: PortAppConfig
    ) -> None:
        logger.info(f"Resyncing {resource_config.kind}")
        tasks: List[Awaitable[ObjectDiff]] = []
        initialize_event_context(EventContext("rsync", resource_config, app_config))
        with logger.contextualize(kind=resource_config.kind):
            if self.__class__._on_resync != BaseIntegration._on_resync:
                tasks.append(self._on_resync(resource_config.kind))

            for wrapper in self.event_strategy["resync"]:
                tasks.append(wrapper(resource_config.kind))

            results = [
                validate_result(task_result)
                for task_result in await asyncio.gather(*tasks)
            ]
            await self._register_raw([(resource_config, results)])

    async def register_state(self, kind: str, entities_state: ObjectDiff) -> None:
        logger.info(f"Registering state for {kind}")
        config = await self.port_app_config.get_port_app_config()
        resource_mappings = [
            resource for resource in config.resources if resource.kind == kind
        ]

        logger.info(f"Found {len(resource_mappings)} resources for {kind}")

        with logger.contextualize(kind=kind):
            await self._register_raw(
                [(mapping, [entities_state]) for mapping in resource_mappings]
            )

    async def trigger_start(self) -> None:
        logger.info("Starting integration")
        if self.started:
            raise Exception("Integration already started")

        if (
            not self.event_strategy["resync"]
            and self.__class__._on_resync == BaseIntegration._on_resync
        ):
            raise NotImplementedError("on_resync is not implemented")

        logger.info("Initializing integration components")
        await self._init_manipulation_instance()
        await self._init_port_app_config_handler_instance()
        await self._init_transport_instance()

        logger.info("Initializing trigger channel")
        await self.trigger_channel.create_trigger_channel()

        logger.info("Initializing integration at port")
        await self.context.port_client.initiate_integration(
            self.context.config.integration.identifier,
            self.context.config.integration.type,
            # ToDo support webhook trigger channel (url)
            {"type": self.context.config.trigger_channel.type},
        )

        self.started = True
        initialize_event_context(EventContext("start"))

        await asyncio.gather(*(listener() for listener in self.event_strategy["start"]))

    async def trigger_action(self, data: Dict[Any, Any]) -> None:
        raise NotImplementedError("trigger_action is not implemented")

    async def trigger_resync(self, _: Dict[Any, Any] | None = None) -> None:
        logger.info("Resync was triggered")
        app_config = await self.port_app_config.get_port_app_config()

        await asyncio.gather(
            *(
                self._resync_resource(resource, app_config)
                for resource in app_config.resources
            )
        )
