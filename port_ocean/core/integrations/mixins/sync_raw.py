import asyncio
import inspect
import typing
from typing import Callable, Awaitable, Any

from loguru import logger

from port_ocean.clients.port.types import UserAgentType
from port_ocean.context.event import TriggerType, event_context, EventType, event
from port_ocean.context.ocean import ocean
from port_ocean.context.resource import resource_context
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.integrations.mixins import HandlerMixin, EventsMixin
from port_ocean.core.integrations.mixins.utils import (
    is_resource_supported,
    unsupported_kind_response,
    resync_generator_wrapper,
    resync_function_wrapper,
)
from port_ocean.core.models import Entity
from port_ocean.core.ocean_types import (
    RAW_RESULT,
    RESYNC_RESULT,
    RawEntityDiff,
    ASYNC_GENERATOR_RESYNC_TYPE,
    RAW_ITEM,
    EntitySelectorDiff,
)
from port_ocean.core.utils import zip_and_sum
from port_ocean.exceptions.core import OceanAbortException


class SyncRawMixin(HandlerMixin, EventsMixin):
    """Mixin class for synchronization of raw constructed entities.

    This mixin class extends the functionality of HandlerMixin and EventsMixin to provide methods for registering,
    unregistering, updating, and syncing raw entities' state changes.

    Note:
        Raw entities are entities with a more primitive structure, usually fetched directly from a resource.
    """

    def __init__(self) -> None:
        HandlerMixin.__init__(self)
        EventsMixin.__init__(self)

    async def _on_resync(self, kind: str) -> RAW_RESULT:
        raise NotImplementedError("on_resync must be implemented")

    async def _get_resource_raw_results(
        self, resource_config: ResourceConfig
    ) -> tuple[RESYNC_RESULT, list[Exception]]:
        logger.info(f"Fetching {resource_config.kind} resync results")

        if not is_resource_supported(
            resource_config.kind, self.event_strategy["resync"]
        ):
            return unsupported_kind_response(
                resource_config.kind, self.available_resync_kinds
            )

        fns = self._collect_resync_functions(resource_config)

        results, errors = await self._execute_resync_tasks(fns, resource_config)

        return results, errors

    def _collect_resync_functions(
        self, resource_config: ResourceConfig
    ) -> list[Callable[[str], Awaitable[RAW_RESULT]]]:
        logger.contextualize(kind=resource_config.kind)

        fns = [
            *self.event_strategy["resync"][resource_config.kind],
            *self.event_strategy["resync"][None],
        ]

        if self.__class__._on_resync != SyncRawMixin._on_resync:
            fns.append(self._on_resync)

        return fns

    async def _execute_resync_tasks(
        self,
        fns: list[Callable[[str], Awaitable[RAW_RESULT]]],
        resource_config: ResourceConfig,
    ) -> tuple[RESYNC_RESULT, list[RAW_RESULT | Exception]]:
        tasks = []
        results = []

        for task in fns:
            if inspect.isasyncgenfunction(task):
                results.append(resync_generator_wrapper(task, resource_config.kind))
            else:
                task = typing.cast(Callable[[str], Awaitable[RAW_RESULT]], task)
                tasks.append(resync_function_wrapper(task, resource_config.kind))

        logger.info(
            f"Found {len(tasks) + len(results)} resync tasks for {resource_config.kind}"
        )

        results_with_error = await asyncio.gather(*tasks, return_exceptions=True)
        results.extend(
            sum(
                [
                    result
                    for result in results_with_error
                    if not isinstance(result, Exception)
                ],
                [],
            )
        )
        errors = [
            result for result in results_with_error if isinstance(result, Exception)
        ]

        logger.info(
            f"Triggered {len(tasks)} tasks for {resource_config.kind}, failed: {len(errors)}"
        )

        return results, errors

    async def _calculate_raw(
        self,
        raw_diff: list[tuple[ResourceConfig, list[RAW_ITEM]]],
        parse_all: bool = False,
    ) -> list[EntitySelectorDiff]:
        return await asyncio.gather(
            *(
                self.entity_processor.parse_items(mapping, results, parse_all)
                for mapping, results in raw_diff
            )
        )

    async def _register_resource_raw(
        self,
        resource: ResourceConfig,
        results: list[dict[Any, Any]],
        user_agent_type: UserAgentType,
        parse_all: bool = False,
    ) -> EntitySelectorDiff:
        objects_diff = await self._calculate_raw([(resource, results)], parse_all)
        await self.entities_state_applier.upsert(
            objects_diff[0].passed, user_agent_type
        )

        return objects_diff[0]

    async def _unregister_resource_raw(
        self,
        resource: ResourceConfig,
        results: list[RAW_ITEM],
        user_agent_type: UserAgentType,
    ) -> list[Entity]:
        objects_diff = await self._calculate_raw([(resource, results)])

        entities_after: list[Entity] = objects_diff[0].passed
        await self.entities_state_applier.delete(entities_after, user_agent_type)
        logger.info("Finished unregistering change")
        return entities_after

    async def _register_in_batches(
        self, resource_config: ResourceConfig, user_agent_type: UserAgentType
    ) -> tuple[list[Entity], list[Exception]]:
        results, errors = await self._get_resource_raw_results(resource_config)
        async_generators: list[ASYNC_GENERATOR_RESYNC_TYPE] = []
        raw_results: RAW_RESULT = []
        for result in results:
            if isinstance(result, dict):
                raw_results.append(result)
            else:
                async_generators.append(result)

        entities = (
            await self._register_resource_raw(
                resource_config, raw_results, user_agent_type
            )
        ).passed

        for generator in async_generators:
            try:
                async for items in generator:
                    entities.extend(
                        (
                            await self._register_resource_raw(
                                resource_config, items, user_agent_type
                            )
                        ).passed
                    )
            except* OceanAbortException as error:
                errors.append(error)

        logger.info(
            f"Finished registering change for {len(results)} raw results for kind: {resource_config.kind}. {len(entities)} entities were affected"
        )
        return entities, errors

    async def register_raw(
        self,
        kind: str,
        results: list[dict[Any, Any]],
        user_agent_type: UserAgentType,
    ) -> list[Entity]:
        """Register raw entities of a specific kind.

        This method registers raw entities of a specific kind into Port.

        Args:
            kind (str): The kind of raw entities being registered.
            results (list[dict[Any, Any]]): The raw entity results to be registered.
            user_agent_type (UserAgentType): The type of user agent.

        Returns:
            list[Entity]: A list of registered entities.
        """
        logger.info(f"Registering state for {kind}")
        config = await self.port_app_config_handler.get_port_app_config()
        resource_mappings = [
            resource for resource in config.resources if resource.kind == kind
        ]

        if not resource_mappings:
            return []

        diffs: list[EntitySelectorDiff] = await asyncio.gather(
            *(
                self._register_resource_raw(resource, results, user_agent_type, True)
                for resource in resource_mappings
            )
        )

        registered_entities, entities_to_delete = zip_and_sum(
            (entities_diff.passed, entities_diff.failed) for entities_diff in diffs
        )

        registered_entities_attributes = {
            (entity.identifier, entity.blueprint) for entity in registered_entities
        }

        filtered_entities_to_delete: list[Entity] = (
            await ocean.port_client.search_batch_entities(
                user_agent_type,
                [
                    entity
                    for entity in entities_to_delete
                    if (entity.identifier, entity.blueprint)
                    not in registered_entities_attributes
                ],
            )
        )

        if filtered_entities_to_delete:
            logger.info(
                f"Deleting {len(filtered_entities_to_delete)} entities that didn't pass any of the selectors"
            )

            await self.entities_state_applier.delete(
                filtered_entities_to_delete, user_agent_type
            )

        return registered_entities

    async def unregister_raw(
        self,
        kind: str,
        results: list[dict[Any, Any]],
        user_agent_type: UserAgentType,
    ) -> list[Entity]:
        """Unregister raw entities of a specific kind.

        This method unregisters raw entities of a specific kind from Port.

        Args:
            kind (str): The kind of raw entities being unregistered.
            results (list[dict[Any, Any]]): The raw entity results to be unregistered.
            user_agent_type (UserAgentType): The type of user agent.

        Returns:
            list[Entity]: A list of unregistered entities.
        """
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
        """Update the difference in state for raw entities of a specific kind.

        This method updates the difference in state for raw entities of a specific kind.

        Args:
            kind (str): The kind of raw entities being updated.
            raw_desired_state (RawEntityDiff): The desired state difference of raw entities.
            user_agent_type (UserAgentType): The type of user agent.
        """
        logger.info(f"Updating state for {kind}")
        config = await self.port_app_config_handler.get_port_app_config()
        resource_mappings = [
            resource for resource in config.resources if resource.kind == kind
        ]

        with logger.contextualize(kind=kind):
            logger.info(f"Found {len(resource_mappings)} resources for {kind}")

            entities_before = await self._calculate_raw(
                [
                    (mapping, raw_desired_state["before"])
                    for mapping in resource_mappings
                ]
            )

            entities_after = await self._calculate_raw(
                [(mapping, raw_desired_state["after"]) for mapping in resource_mappings]
            )

            entities_before_flatten: list[Entity] = sum(
                (entities_diff.passed for entities_diff in entities_before), []
            )

            entities_after_flatten: list[Entity] = sum(
                (entities_diff.passed for entities_diff in entities_after), []
            )

            await self.entities_state_applier.apply_diff(
                {"before": entities_before_flatten, "after": entities_after_flatten},
                user_agent_type,
            )

    async def sync_raw_all(
        self,
        _: dict[Any, Any] | None = None,
        trigger_type: TriggerType = "machine",
        user_agent_type: UserAgentType = UserAgentType.exporter,
        silent: bool = True,
    ) -> None:
        """Perform a full synchronization of raw entities.

        This method performs a full synchronization of raw entities, including registration, unregistration,
        and state updates.

        Args:
            _ (dict[Any, Any] | None): Unused parameter.
            trigger_type (TriggerType): The type of trigger for the synchronization.
            user_agent_type (UserAgentType): The type of user agent.
            silent (bool): Whether to raise exceptions or handle them silently.
        """
        logger.info("Resync was triggered")
        async with event_context(
            EventType.RESYNC,
            trigger_type=trigger_type,
        ):
            # If a resync is triggered due to a mappings change, we want to make sure that we have the updated version
            # rather than the old cache
            app_config = await self.port_app_config_handler.get_port_app_config(
                use_cache=False
            )

            creation_results: list[tuple[list[Entity], list[Exception]]] = []

            try:
                for resource in app_config.resources:
                    # create resource context per resource kind, so resync method could have access to the resource
                    # config as we might have multiple resources in the same event
                    async with resource_context(resource):
                        task = asyncio.get_event_loop().create_task(
                            self._register_in_batches(resource, user_agent_type)
                        )

                        event.on_abort(lambda: task.cancel())

                        creation_results.append(await task)
            except asyncio.CancelledError as e:
                logger.warning("Resync aborted successfully")
            else:
                logger.info("Starting resync diff calculation")
                flat_created_entities, errors = zip_and_sum(creation_results) or [
                    [],
                    [],
                ]

                if errors:
                    message = f"Resync failed with {len(errors)}. Skipping delete phase due to incomplete state"
                    error_group = ExceptionGroup(
                        f"Resync failed with {len(errors)}. Skipping delete phase due to incomplete state",
                        errors,
                    )
                    if not silent:
                        raise error_group

                    logger.error(message, exc_info=error_group)
                else:
                    entities_at_port = await ocean.port_client.search_entities(
                        user_agent_type
                    )
                    logger.info(
                        f"Running resync diff calculation, number of entities found at Port: {len(entities_at_port)}, number of entities found during sync: {len(flat_created_entities)}"
                    )
                    await self.entities_state_applier.delete_diff(
                        {"before": entities_at_port, "after": flat_created_entities},
                        user_agent_type,
                    )
