import asyncio
from typing import Set
from loguru import logger
from port_ocean.clients.port.types import UserAgentType
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventRawResults
from port_ocean.core.integrations.mixins.handler import HandlerMixin
from port_ocean.core.models import Entity
from port_ocean.core.ocean_types import RAW_ITEM, CalculationResult
from port_ocean.context.ocean import ocean
from port_ocean.context.event import event


class LiveEventsMixin(HandlerMixin):

    async def export_raw_event_results_to_entities(self, webhook_events_data: list[WebhookEventRawResults]) -> None:
        """Process the webhook event data collected from multiple processors and export it.

        Args:
            webhook_events_data: List of WebhookEventData objects to process
        """
        exported_entities: list[Entity] = []

        exported_entities_from_export = await self._export_resources(webhook_events_data)
        exported_entities.extend(exported_entities_from_export)

        await self._delete_resources(webhook_events_data, exported_entities)

    async def _export(self, resource_mapping: ResourceConfig, raw_item: RAW_ITEM) -> tuple[bool, list[Entity]]:
        """Export a single resource mapping with the given raw item.

        Args:
            resource_mapping: The resource configuration to use for processing
            raw_item: The raw data item to process

        Returns:
            tuple containing:
                - bool: Whether the export succeeded
                - list[str]: List of exported entity identifiers
        """
        try:
            calculation_results = await self.entity_processor.parse_items(
                resource_mapping, [raw_item], parse_all=True, send_raw_data_examples_amount=0
            )

            if not calculation_results or len(calculation_results.entity_selector_diff.passed)== 0:
                logger.info(f"No entities passed selector for resource: {resource_mapping.kind}")
                return True, []

            upserted_entities = await self.entities_state_applier.upsert(calculation_results.entity_selector_diff.passed, UserAgentType.exporter)
            logger.info("Upserted entities at export", upserted_entities=upserted_entities)
            return True, upserted_entities

        except Exception as e:
            logger.error(f"Error exporting resource {resource_mapping.kind}: {str(e)}")
            return False, []

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

    def _did_all_entities_filtered_out_at_export(self, export_succeded: bool, exported_entities: list[Entity]) -> bool:
        return export_succeded and len(exported_entities) == 0

    async def _get_entities_to_delete(self, resource_mapping: ResourceConfig, raw_item: RAW_ITEM) -> list[Entity]:
        calculation_results = await self.entity_processor.parse_items(
                    resource_mapping, [raw_item], parse_all=True, send_raw_data_examples_amount=0
                )
        if len(calculation_results.entity_selector_diff.failed) == 1 and await self._does_entity_exists(calculation_results.entity_selector_diff.failed[0]):
            return calculation_results.entity_selector_diff.failed
        return []

    async def _export_resources(self, webhook_events_data: list[WebhookEventRawResults]) -> list[tuple[str, str]]:
        entities_to_delete: list[Entity] = []
        blueprints_to_keep: Set[tuple[str, str]] = set()

        for webhook_event_data in webhook_events_data:
            if webhook_event_data.updated_raw_results:
                for raw_item in webhook_event_data.updated_raw_results:
                    logger.info("Tring to export single resource", raw_item=raw_item)
                    export_succeded, exported_entities = await self._export(webhook_event_data.resource, raw_item)
                    if self._did_all_entities_filtered_out_at_export(export_succeded, exported_entities):
                        logger.info("No entities passed selector for resource", resource=webhook_event_data.resource)
                        entities_to_delete.extend(await self._get_entities_to_delete(webhook_event_data.resource, raw_item))
                    else:
                        for entity in exported_entities:
                            logger.info("keeping entity from deletion", entity=entity)
                            blueprints_to_keep.add((entity.blueprint, entity.identifier))

        entities_to_delete_filtered_by_kept_blueprints = [entity for entity in entities_to_delete if (entity.blueprint, entity.identifier) not in blueprints_to_keep]

        try:
            if entities_to_delete_filtered_by_kept_blueprints:
                logger.info(f"Deleting entities after filtering out the bluepprint entities to keep",
                    deleted_entities_count=len(entities_to_delete_filtered_by_kept_blueprints))
                await self.entities_state_applier.delete(entities_to_delete_filtered_by_kept_blueprints, UserAgentType.exporter)
            return list(blueprints_to_keep)
        except Exception as e:
            logger.error(f"Failed to delete entities: {str(e)}")

    async def _delete_resources(self, webhook_events_data: list[WebhookEventRawResults], exported_blueprints: list[tuple[str, str]]) -> None:
        entities_to_delete: list[Entity] = []

        for webhook_event_data in webhook_events_data:
            if webhook_event_data.deleted_raw_results:
                for raw_item in webhook_event_data.deleted_raw_results:
                    calculation_results = await self.entity_processor.parse_items(
                        webhook_event_data.resource, [raw_item], parse_all=True, send_raw_data_examples_amount=0
                    )
                    entities_to_delete.extend([entity for entity in calculation_results.entity_selector_diff.passed
                                 if (entity.blueprint, entity.identifier) not in exported_blueprints])

        try:
            if entities_to_delete:
                logger.info("Deleting entities", entities_to_delete=entities_to_delete)
                await self.entities_state_applier.delete(entities_to_delete, UserAgentType.exporter)
        except Exception as e:
            logger.error(f"Failed to delete entities: {str(e)}")
