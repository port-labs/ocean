import asyncio
from collections import defaultdict

from loguru import logger

from port_ocean.clients.port.types import UserAgentType
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.integrations.mixins.handler import HandlerMixin
from port_ocean.core.models import Entity
from port_ocean.core.utils.entity_topological_sorter import (
    order_by_entities_dependencies,
)


class SyncMixin(HandlerMixin):
    """Mixin class for writing already-constructed entities straight to Port.

    No mapping is applied: use this only for entities whose shape is defined by the source
    itself (e.g. GitOps `port.yml` files). Raw data must go through `register_raw` so the
    data-source-processor maps it.
    """

    def __init__(self) -> None:
        HandlerMixin.__init__(self)

    async def register(
        self,
        entities: list[Entity],
        user_agent_type: UserAgentType,
    ) -> list[Entity]:
        """Upsert entities into Port.

        Args:
            entities (list[Entity]): List of entities to be registered.
            user_agent_type (UserAgentType): The type of user agent.

        Returns:
            list[Entity]: The entities Port accepted.
        """
        logger.info(f"Upserting {len(entities)} entities")
        request_options = event.port_app_config.get_port_request_options()
        blueprint_groups: dict[str, list[Entity]] = defaultdict(list)
        for entity in entities:
            blueprint_groups[entity.blueprint].append(entity)

        upserted_entities: list[Entity] = []
        for blueprint_entities in blueprint_groups.values():
            results = await ocean.port_client.upsert_entities_in_batches(
                blueprint_entities,
                request_options,
                user_agent_type,
                should_raise=False,
            )
            upserted_entities.extend(
                entity for is_upserted, entity in results if is_upserted
            )
        logger.info("Finished registering change")
        return upserted_entities

    async def unregister(
        self, entities: list[Entity], user_agent_type: UserAgentType
    ) -> None:
        """Delete entities from Port.

        Args:
            entities (list[Entity]): List of entities to be unregistered.
            user_agent_type (UserAgentType): The type of user agent.
        """
        logger.info(f"Deleting {len(entities)} entities")
        request_options = event.port_app_config.get_port_request_options()

        if event.port_app_config.delete_dependent_entities:
            blueprint_groups: dict[str, list[str]] = defaultdict(list)
            for entity in entities:
                blueprint_groups[entity.blueprint].append(entity.identifier)

            # port cascades deletion of dependent entities, so we can delete in bulk
            await asyncio.gather(
                *(
                    ocean.port_client.bulk_delete_entities(
                        blueprint,
                        identifiers,
                        request_options,
                        user_agent_type,
                        should_raise=False,
                    )
                    for blueprint, identifiers in blueprint_groups.items()
                )
            )
        else:
            # delete entities one by one in topological order to prevent deletion
            # of entities that are still referenced by other entities
            for entity in order_by_entities_dependencies(entities):
                await ocean.port_client.bulk_delete_entities(
                    entity.blueprint,
                    [entity.identifier],
                    request_options,
                    user_agent_type,
                    should_raise=False,
                )
        logger.info("Finished unregistering change")
