import asyncio
from itertools import chain
from typing import Any, Awaitable

from loguru import logger

from port_ocean.clients.port.types import UserAgentType
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.integrations.mixins.events import EventsMixin
from port_ocean.core.integrations.mixins.handler import HandlerMixin
from port_ocean.core.models import Entity
from port_ocean.core.utils import validate_result, zip_and_sum
from port_ocean.types import RawEntityDiff, EntityDiff


class SyncMixin(HandlerMixin, EventsMixin):
    def __init__(self) -> None:
        HandlerMixin.__init__(self)
        EventsMixin.__init__(self)

    async def register(
        self,
        entities: list[Entity],
        user_agent_type: UserAgentType,
    ) -> None:
        await self.transport.upsert(entities, user_agent_type)
        logger.info("Finished registering change")

    async def unregister(
        self, entities: list[Entity], user_agent_type: UserAgentType
    ) -> None:
        await self.transport.delete(entities, user_agent_type)
        logger.info("Finished unregistering change")

    async def sync(
        self,
        entities: list[Entity],
        user_agent_type: UserAgentType,
    ) -> None:
        await self.transport.upsert(entities, user_agent_type)
        await self.transport.delete_non_existing(entities, user_agent_type)

        logger.info("Finished syncing change")


class SyncRawMixin(HandlerMixin, EventsMixin):
    def __init__(self) -> None:
        HandlerMixin.__init__(self)
        EventsMixin.__init__(self)

    async def _on_resync(self, kind: str) -> list[dict[Any, Any]]:
        raise NotImplementedError("on_resync must be implemented")

    async def _calculate_raw(
        self, raw_diff: list[tuple[ResourceConfig, RawEntityDiff]]
    ) -> list[EntityDiff]:
        logger.info("Calculating diff in entities between states")
        return await asyncio.gather(
            *[
                self.manipulation.parse_items(mapping, results)
                for mapping, results in raw_diff
            ]
        )

    async def _get_resource_raw_results(
        self, resource_config: ResourceConfig
    ) -> tuple[ResourceConfig, list[dict[Any, Any]]]:
        logger.info(f"Resyncing {resource_config.kind}")
        tasks: list[Awaitable[list[dict[Any, Any]]]] = []
        with logger.contextualize(kind=resource_config.kind):
            if self.__class__._on_resync != SyncRawMixin._on_resync:
                tasks.append(self._on_resync(resource_config.kind))

            fns = [
                *self.event_strategy["resync"][resource_config.kind],
                *self.event_strategy["resync"][None],
            ]

            for wrapper in fns:
                tasks.append(wrapper(resource_config.kind))

            logger.info(f"Found {len(tasks)} resync tasks for {resource_config.kind}")
            results: list[dict[Any, Any]] = list(
                chain.from_iterable(
                    [
                        validate_result(task_result)
                        for task_result in await asyncio.gather(*tasks)
                    ]
                )
            )

            logger.info(f"Triggered {len(tasks)} tasks for {resource_config.kind}")
            return resource_config, results

    async def _register_resource_raw(
        self,
        resource: ResourceConfig,
        results: list[dict[Any, Any]],
        user_agent_type: UserAgentType,
    ) -> list[Entity]:
        objects_diff = await self._calculate_raw(
            [
                (
                    resource,
                    {
                        "before": [],
                        "after": results,
                    },
                )
            ]
        )

        entities_after: list[Entity] = objects_diff[0]["after"]
        await self.transport.upsert(entities_after, user_agent_type)
        logger.info("Finished registering change")
        return entities_after

    async def _unregister_resource_raw(
        self,
        resource: ResourceConfig,
        results: list[dict[Any, Any]],
        user_agent_type: UserAgentType,
    ) -> list[Entity]:
        objects_diff = await self._calculate_raw(
            [
                (
                    resource,
                    {
                        "before": results,
                        "after": [],
                    },
                )
            ]
        )

        entities_after: list[Entity] = objects_diff[0]["before"]
        await self.transport.delete(entities_after, user_agent_type)
        logger.info("Finished unregistering change")
        return entities_after

    async def register_raw(
        self,
        kind: str,
        results: list[dict[Any, Any]],
        user_agent_type: UserAgentType,
    ) -> list[Entity]:
        logger.info(f"Registering state for {kind}")
        config = await self.port_app_config_handler.get_port_app_config()
        resource_mappings = [
            resource for resource in config.resources if resource.kind == kind
        ]

        return await asyncio.gather(
            *(
                self._register_resource_raw(resource, results, user_agent_type)
                for resource in resource_mappings
            )
        )

    async def unregister_raw(
        self,
        kind: str,
        results: list[dict[Any, Any]],
        user_agent_type: UserAgentType,
    ) -> list[Entity]:
        logger.info(f"Registering state for {kind}")
        config = await self.port_app_config_handler.get_port_app_config()
        resource_mappings = [
            resource for resource in config.resources if resource.kind == kind
        ]

        return await asyncio.gather(
            *(
                self._unregister_resource_raw(resource, results, user_agent_type)
                for resource in resource_mappings
            )
        )

    async def update_raw_diff(
        self,
        kind: str,
        raw_desired_state: RawEntityDiff,
        user_agent_type: UserAgentType,
    ) -> None:
        logger.info(f"Registering state for {kind}")
        config = await self.port_app_config_handler.get_port_app_config()
        resource_mappings = [
            resource for resource in config.resources if resource.kind == kind
        ]

        with logger.contextualize(kind=kind):
            logger.info(f"Found {len(resource_mappings)} resources for {kind}")

            objects_diff = await self._calculate_raw(
                [(mapping, raw_desired_state) for mapping in resource_mappings]
            )

            entities_before, entities_after = zip_and_sum(
                (
                    (entities_change["before"], entities_change["after"])
                    for entities_change in objects_diff
                )
            )

            await self.transport.update_diff(
                {"before": entities_before, "after": entities_after}, user_agent_type
            )
