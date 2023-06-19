import asyncio
from typing import (
    List,
    Dict,
    Any,
    Tuple,
    Awaitable,
)

from loguru import logger

from port_ocean.context.event import (
    event_context,
)
from port_ocean.context.integration import PortOceanContext
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
)
from port_ocean.core.integrations.mixins import HandlerMixin, EventsMixin
from port_ocean.core.models import Entity, Blueprint
from port_ocean.core.trigger_channel.trigger_channel_factory import (
    TriggerChannelFactory,
)
from port_ocean.core.utils import (
    validate_result,
    get_object_diff,
    is_same_entity,
    is_same_blueprint,
)
from port_ocean.types import (
    RawObjectDiff,
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

    async def _on_resync(self, kind: str) -> RawObjectDiff:
        raise NotImplementedError("on_resync must be implemented")

    async def _register_raw(
        self, raw_diff: List[Tuple[ResourceConfig, List[RawObjectDiff]]]
    ) -> None:
        logger.info("Calculating diff in entities and blueprints between states")
        objects_diff = await asyncio.gather(
            *[
                self.manipulation.get_diff(mapping, results)
                for mapping, results in raw_diff
            ]
        )

        await self.port_client.update_diff(objects_diff)
        logger.info("Finished registering change")

    async def _resync_resource(
        self, resource_config: ResourceConfig
    ) -> Tuple[ResourceConfig, List[RawObjectDiff]]:
        logger.info(f"Resyncing {resource_config.kind}")
        tasks: List[Awaitable[RawObjectDiff]] = []
        with logger.contextualize(kind=resource_config.kind):
            if self.__class__._on_resync != BaseIntegration._on_resync:
                tasks.append(self._on_resync(resource_config.kind))

            for wrapper in self.event_strategy["resync"]:
                tasks.append(wrapper(resource_config.kind))

            logger.info(f"Found {len(tasks)} resync tasks for {resource_config.kind}")
            results = [
                validate_result(task_result)
                for task_result in await asyncio.gather(*tasks)
            ]

            logger.info(f"Triggered {len(tasks)} tasks for {resource_config.kind}")
            return resource_config, results

    async def register_raw(self, kind: str, entities_state: RawObjectDiff) -> None:
        logger.info(f"Registering state for {kind}")
        config = await self.port_app_config_handler.get_port_app_config()
        resource_mappings = [
            resource for resource in config.resources if resource.kind == kind
        ]

        async with event_context(kind):
            with logger.contextualize(kind=kind):
                logger.info(f"Found {len(resource_mappings)} resources for {kind}")

                await self._register_raw(
                    [(mapping, [entities_state]) for mapping in resource_mappings]
                )

    async def register(
        self, entities: ObjectDiff[Entity], blueprints: ObjectDiff[Blueprint]
    ) -> None:
        entities_diff = get_object_diff(
            entities["before"], entities["after"], is_same_entity
        )
        blueprints_diff = get_object_diff(
            blueprints["before"], blueprints["after"], is_same_blueprint
        )

        await self.port_client.update_diff([(entities_diff, blueprints_diff)])
        logger.info("Finished registering change")

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

        async with event_context("start"):
            await asyncio.gather(
                *(listener() for listener in self.event_strategy["start"])
            )

    async def trigger_action(self, data: Dict[Any, Any]) -> None:
        raise NotImplementedError("trigger_action is not implemented")

    async def trigger_resync(self, _: Dict[Any, Any] | None = None) -> None:
        logger.info("Resync was triggered")
        app_config = await self.port_app_config_handler.get_port_app_config()

        async with event_context("resync", app_config):
            evaluations = await asyncio.gather(
                *(self._resync_resource(resource) for resource in app_config.resources)
            )

            await self._register_raw(
                [(mapping, results) for mapping, results in evaluations]
            )
