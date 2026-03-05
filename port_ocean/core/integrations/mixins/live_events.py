from typing import AsyncGenerator

from loguru import logger
from port_ocean.clients.port.types import UserAgentType
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventRawResults
from port_ocean.core.integrations.mixins.handler import HandlerMixin
from port_ocean.core.integrations.mixins.utils import handle_items_to_parse
from port_ocean.core.models import Entity
from port_ocean.core.ocean_types import RAW_ITEM
from port_ocean.context.ocean import ocean



class LiveEventsMixin(HandlerMixin):

    async def sync_raw_results(self, webhook_events_raw_result: list[WebhookEventRawResults]) -> None:
        """Process the webhook event raw results collected from multiple processors and export it.

        Args:
            webhook_events_raw_result: List of WebhookEventRawResults objects to process
        """
        entities_to_create, entities_to_delete = await self._parse_raw_event_results_to_entities(webhook_events_raw_result)
        if entities_to_create:
            await self.entities_state_applier.upsert(entities_to_create, UserAgentType.exporter)
        if entities_to_delete:
            await self._delete_entities(entities_to_delete)


    async def _expand_raw_item(
        self, raw_item: RAW_ITEM, resource: ResourceConfig
    ) -> AsyncGenerator[list[RAW_ITEM], None]:
        if resource.port.items_to_parse:
            async for batch in handle_items_to_parse(
                [raw_item],
                resource.port.items_to_parse_name,
                resource.port.items_to_parse,
                resource.port.items_to_parse_top_level_transform,
            ):
                yield batch
        else:
            yield [raw_item]

    async def _parse_raw_event_results_to_entities(self, webhook_events_raw_result: list[WebhookEventRawResults]) -> tuple[list[Entity], list[Entity]]:
        """Parse the webhook event raw results and return a list of entities.

        Args:
            webhook_events_raw_result: List of WebhookEventRawResults objects to process
        """
        entities: list[Entity] = []
        entities_not_passed: list[Entity] = []
        entities_to_delete: list[Entity] = []
        for webhook_event_raw_result in webhook_events_raw_result:
            resource = webhook_event_raw_result.resource
            for raw_item in webhook_event_raw_result.updated_raw_results:
                async for batch in self._expand_raw_item(raw_item, resource):
                    calculation_results = await self.entity_processor.parse_items(
                        resource, batch, parse_all=True, send_raw_data_examples_amount=0
                    )
                    entities.extend(calculation_results.entity_selector_diff.passed)
                    entities_not_passed.extend(calculation_results.entity_selector_diff.failed)

            for raw_item in webhook_event_raw_result.deleted_raw_results:
                async for batch in self._expand_raw_item(raw_item, resource):
                    deletion_results = await self.entity_processor.parse_items(
                        resource, batch, parse_all=True, send_raw_data_examples_amount=0
                    )
                    entities_to_delete.extend(deletion_results.entity_selector_diff.passed)

        entities_to_remove = []
        for entity in entities_to_delete + entities_not_passed:
            if (entity.blueprint, entity.identifier) not in [(entity.blueprint, entity.identifier) for entity in entities]:
                entities_to_remove.append(entity)

        logger.info(f"Found {len(entities_to_remove)} entities to remove {', '.join(f'{entity.blueprint}/{entity.identifier}' for entity in entities_to_remove)}")
        logger.info(f"Found {len(entities)} entities to upsert {', '.join(f'{entity.blueprint}/{entity.identifier}' for entity in entities)}")
        return entities, entities_to_remove

    async def _does_entity_exists(self, entity: Entity) -> bool:
        """Check if this integration is the owner of the given entity.

        Args:
            entity: The entity to check ownership for

        Returns:
            bool: True if this integration is the owner of the entity, False otherwise
        """
        query = {
            "combinator": "and",
            "rules": [
                {
                    "property": "$identifier",
                    "operator": "=",
                    "value": entity.identifier
                },
                {
                    "property": "$blueprint",
                    "operator": "=",
                    "value": entity.blueprint
                }
            ]
        }
        entities_at_port = await ocean.port_client.search_entities(
            UserAgentType.exporter,
            query
        )
        return len(entities_at_port) > 0

    async def _delete_entities(self, entities: list[Entity]) -> None:
        for entity in entities:
            if await self._does_entity_exists(entity):
                await self.entities_state_applier.delete([entity], UserAgentType.exporter)
