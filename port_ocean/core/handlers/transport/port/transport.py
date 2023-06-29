import asyncio
from itertools import chain

from loguru import logger

from port_ocean.clients.port.types import UserAgentType
from port_ocean.context.event import event
from port_ocean.core.handlers.manipulation.base import EntityPortDiff
from port_ocean.core.handlers.transport.base import BaseTransport
from port_ocean.core.handlers.transport.port.order_by_entities_dependencies import (
    order_by_entities_dependencies,
)
from port_ocean.core.handlers.transport.port.validate_entity_relations import (
    validate_entity_relations,
)
from port_ocean.core.models import Entity
from port_ocean.core.types import EntityDiff
from port_ocean.core.utils import is_same_entity, get_unique, get_port_diff


class HttpPortTransport(BaseTransport):
    async def _validate_delete_dependent_entities(self, entities: list[Entity]) -> None:
        logger.info("Validated deleted entities")
        if not event.port_app_config.delete_dependent_entities:
            deps = await asyncio.gather(
                *[
                    self.context.port_client.search_dependent_entities(entity)
                    for entity in entities
                ]
            )
            new_dependent = get_unique(
                [
                    entity
                    for entity in chain.from_iterable(deps)
                    if not any([is_same_entity(item, entity) for item in entities])
                ]
            )

            if new_dependent:
                raise Exception(
                    f"Must enable delete_dependent_entities flag or delete also dependent entities:"
                    f" {[(dep.blueprint, dep.identifier) for dep in new_dependent]}"
                )

    async def _validate_entity_diff(self, diff: EntityPortDiff) -> None:
        config = event.port_app_config
        await self._validate_delete_dependent_entities(diff.deleted)
        modified_or_created_entities = diff.modified + diff.created
        logger.info("Validating modified or created entities")

        await asyncio.gather(
            *[
                self.context.port_client.validate_entity_payload(
                    entity,
                    {
                        "merge": config.enable_merge_entity,
                        "create_missing_related_entities": config.create_missing_related_entities,
                    },
                )
                for entity in modified_or_created_entities
            ]
        )
        await validate_entity_relations(diff, self.context.port_client)

    async def update_diff(
        self,
        entities: EntityDiff,
        user_agent_type: UserAgentType | None = None,
    ) -> None:
        diff = get_port_diff(entities["before"], entities["after"])

        logger.info(
            f"Registering entity diff (created: {len(diff.created)}, deleted: {len(diff.deleted)}, modified: {len(diff.modified)})"
        )
        await self._validate_entity_diff(diff)

        user_agent_type = user_agent_type or self.DEFAULT_USER_AGENT_TYPE
        await self.delete(diff.deleted, user_agent_type)
        await self.upsert(diff.created, user_agent_type)
        await self.upsert(diff.modified, user_agent_type)

    async def upsert(
        self, entities: list[Entity], user_agent_type: UserAgentType
    ) -> None:
        ordered_created_entities = reversed(order_by_entities_dependencies(entities))
        for entity in ordered_created_entities:
            await self.context.port_client.upsert_entity(
                entity,
                event.port_app_config.get_port_request_options(),
                user_agent_type,
            )

    async def delete(
        self, entities: list[Entity], user_agent_type: UserAgentType
    ) -> None:
        ordered_deleted_entities = order_by_entities_dependencies(entities)

        await asyncio.gather(
            *[
                self.context.port_client.delete_entity(entity, user_agent_type)
                for entity in ordered_deleted_entities
            ]
        )

    async def delete_non_existing(
        self, excluded_entities: list[Entity], user_agent_type: UserAgentType
    ) -> None:
        entities_at_port = await self.context.port_client.search_entities(
            user_agent_type
        )
        diff = get_port_diff(entities_at_port, excluded_entities)
        await self._validate_entity_diff(diff)

        ordered_deleted_entities = order_by_entities_dependencies(diff.deleted)

        await asyncio.gather(
            *[
                self.context.port_client.delete_entity(entity, user_agent_type)
                for entity in ordered_deleted_entities
            ]
        )
