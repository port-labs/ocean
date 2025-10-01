from collections import defaultdict
from loguru import logger

from port_ocean.clients.port.types import UserAgentType
from port_ocean.context.event import event
from port_ocean.core.handlers.entities_state_applier.base import (
    BaseEntitiesStateApplier,
)
from port_ocean.core.handlers.entities_state_applier.port.get_related_entities import (
    get_related_entities,
)
from port_ocean.context.ocean import ocean
from port_ocean.helpers.metric.metric import MetricType, MetricPhase
from port_ocean.helpers.metric.utils import TimeMetric
from port_ocean.core.models import Entity
from port_ocean.core.ocean_types import EntityDiff
from port_ocean.core.utils.entity_topological_sorter import EntityTopologicalSorter
from port_ocean.core.utils.utils import is_same_entity, get_port_diff


class HttpEntitiesStateApplier(BaseEntitiesStateApplier):
    """Applies and manages changes to entities' state using HTTP requests.

    This class extends the BaseEntitiesStateApplier and provides concrete implementations
    for applying changes, deleting entities, upserting entities, and handling entity diffs
    through HTTP requests.
    """

    @TimeMetric(MetricPhase.DELETE)
    async def _safe_delete(
        self,
        entities_to_delete: list[Entity],
        entities_to_protect: list[Entity],
        user_agent_type: UserAgentType,
    ) -> None:
        if not entities_to_delete:
            return

        related_entities = await get_related_entities(
            entities_to_protect, self.context.port_client
        )

        allowed_entities_to_delete = []

        for entity_to_delete in entities_to_delete:
            is_part_of_related = any(
                is_same_entity(entity, entity_to_delete) for entity in related_entities
            )
            is_part_of_created = any(
                is_same_entity(entity, entity_to_delete)
                for entity in entities_to_protect
            )
            if is_part_of_related:
                if event.port_app_config.create_missing_related_entities:
                    logger.info(
                        f"Skipping entity {(entity_to_delete.identifier, entity_to_delete.blueprint)} because it is "
                        f"related to created entities and create_missing_related_entities is enabled"
                    )
                else:
                    allowed_entities_to_delete.append(entity_to_delete)
            elif not is_part_of_created:
                allowed_entities_to_delete.append(entity_to_delete)

        await self.delete(allowed_entities_to_delete, user_agent_type)

    async def apply_diff(
        self,
        entities: EntityDiff,
        user_agent_type: UserAgentType,
    ) -> None:
        diff = get_port_diff(entities["before"], entities["after"])
        kept_entities = diff.created + diff.modified

        logger.info(
            f"Updating entity diff (created: {len(diff.created)}, deleted: {len(diff.deleted)}, modified: {len(diff.modified)})"
        )
        modified_entities = await self.upsert(kept_entities, user_agent_type)

        await self._safe_delete(diff.deleted, modified_entities, user_agent_type)

    async def delete_diff(
        self,
        entities: EntityDiff,
        user_agent_type: UserAgentType,
        entity_deletion_threshold: float | None = None,
    ) -> None:
        diff = get_port_diff(entities["before"], entities["after"])

        if not diff.deleted:
            ocean.metrics.inc_metric(
                name=MetricType.OBJECT_COUNT_NAME,
                labels=[
                    ocean.metrics.current_resource_kind(),
                    MetricPhase.DELETE,
                    MetricPhase.DeletionResult.DELETED,
                ],
                value=0,
            )
            return

        kept_entities = diff.created + diff.modified

        logger.info(
            f"Determining entities to delete ({len(diff.deleted)}/{len(kept_entities)})",
            deleting_entities=len(diff.deleted),
            keeping_entities=len(kept_entities),
            entity_deletion_threshold=entity_deletion_threshold,
        )

        deletion_rate = len(diff.deleted) / len(entities["before"])
        if (
            entity_deletion_threshold is not None
            and deletion_rate <= entity_deletion_threshold
        ):
            await self._safe_delete(diff.deleted, kept_entities, user_agent_type)
            ocean.metrics.inc_metric(
                name=MetricType.OBJECT_COUNT_NAME,
                labels=[
                    ocean.metrics.current_resource_kind(),
                    MetricPhase.DELETE,
                    MetricPhase.DeletionResult.DELETED,
                ],
                value=len(diff.deleted),
            )
        else:
            logger.info(
                f"Skipping deletion of entities with deletion rate {deletion_rate}",
                deletion_rate=deletion_rate,
                deleting_entities=len(diff.deleted),
                total_entities=len(entities),
            )

    async def upsert(
        self, entities: list[Entity], user_agent_type: UserAgentType
    ) -> list[Entity]:
        logger.info(f"Upserting {len(entities)} entities")
        modified_entities: list[Entity] = []

        blueprint_groups: dict[str, list[Entity]] = defaultdict(list)
        for entity in entities:
            blueprint_groups[entity.blueprint].append(entity)

        for blueprint_entities in blueprint_groups.values():
            upserted_entities = (
                await self.context.port_client.upsert_entities_in_batches(
                    blueprint_entities,
                    event.port_app_config.get_port_request_options(),
                    user_agent_type,
                    should_raise=False,
                )
            )

            for is_upserted, entity in upserted_entities:
                if is_upserted:
                    modified_entities.append(entity)
                else:
                    event.entity_topological_sorter.register_entity(entity)

        return modified_entities

    async def delete(
        self, entities: list[Entity], user_agent_type: UserAgentType
    ) -> None:
        logger.info(f"Deleting {len(entities)} entities")
        if event.port_app_config.delete_dependent_entities:
            await self.context.port_client.batch_delete_entities(
                entities,
                event.port_app_config.get_port_request_options(),
                user_agent_type,
                should_raise=False,
            )
        else:
            ordered_deleted_entities = (
                EntityTopologicalSorter.order_by_entities_dependencies(entities)
            )

            for entity in ordered_deleted_entities:
                await self.context.port_client.delete_entity(
                    entity,
                    event.port_app_config.get_port_request_options(),
                    user_agent_type,
                    should_raise=False,
                )
