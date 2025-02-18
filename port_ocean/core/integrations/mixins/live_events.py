import asyncio
from typing import Set
from loguru import logger
from port_ocean.clients.port.types import UserAgentType
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventData
from port_ocean.core.integrations.mixins.handler import HandlerMixin
from port_ocean.core.models import Entity
from port_ocean.core.ocean_types import RAW_ITEM, CalculationResult
from port_ocean.context.ocean import ocean
from port_ocean.context.event import event


class LiveEventsMixin(HandlerMixin):

    async def export_raw_event_results_to_entities(self, webhook_events_data: list[WebhookEventData]) -> None:
        """Process the webhook event data collected from multiple processors and export it.

        Args:
            webhook_events_data: List of WebhookEventData objects to process
        """
        for webhook_event_data in webhook_events_data:
            resource_mappings = await self._get_live_event_resources(
                webhook_event_data.kind
            )

            exported_entities: list[Entity] = []

            for raw_item in webhook_event_data.data_to_update:
                exported_entities_from_export = await self._export_single_resource(resource_mappings, raw_item)
                exported_entities.extend(exported_entities_from_export)

            await self._delete_entities(resource_mappings, exported_entities, webhook_event_data.data_to_delete)



    async def _get_live_event_resources(self, kind: str) -> list[ResourceConfig]:
        try:
            app_config = event.port_app_config
            logger.info(
                f"process data will use the following mappings: {app_config.dict()}"
            )

            resource_mappings = [
                resource for resource in app_config.resources if resource.kind == kind
            ]

            if not resource_mappings:
                logger.warning(f"No resource mappings found for kind: {kind}")
                return []

            return resource_mappings
        except Exception as e:
            logger.error(f"Error getting live event resources: {str(e)}")
            raise

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

    async def _export_single_resource(self, resource_mappings: list[ResourceConfig], raw_item: RAW_ITEM) -> list[Entity]:
        entities_to_delete: list[Entity] = []
        blueprints_to_keep: Set[str] = set()

        logger.info("Exporting single resource", raw_item=raw_item, resource_mappings_count=len(resource_mappings))
        for resource_mapping in resource_mappings:
            export_succeded, exported_entities = await self._export(resource_mapping, raw_item)
            if self._did_all_entities_filtered_out_at_export(export_succeded, exported_entities):
                entities_to_delete.extend(await self._get_entities_to_delete(resource_mapping, raw_item))
            else:
                for entity in exported_entities:
                    blueprints_to_keep.add(entity.blueprint)

        entities_to_delete_filtered_by_kept_blueprints = [entity for entity in entities_to_delete if entity.blueprint not in blueprints_to_keep]

        logger.info(f"Deleting entities after filtering out the bluepprint entities to keep",
                    deleted_entities_count=len(entities_to_delete_filtered_by_kept_blueprints))
        try:
            if entities_to_delete_filtered_by_kept_blueprints:
                await self.entities_state_applier.delete(entities_to_delete_filtered_by_kept_blueprints, UserAgentType.exporter)
            return exported_entities
        except Exception as e:
            logger.error(f"Failed to delete entities: {str(e)}")

    async def _delete_entities(self, resource_mappings: list[ResourceConfig],upserted_entities: list[Entity], raw_items_to_delete: list[RAW_ITEM]) -> None:
        entities_to_delete: list[Entity] = []
        if len(raw_items_to_delete) == 0:
            return
        for resource_mapping in resource_mappings:
            calculation_results = await self.entity_processor.parse_items(
                resource_mapping, raw_items_to_delete, parse_all=True, send_raw_data_examples_amount=0
            )
            entities_to_delete.extend([entity for entity in calculation_results.entity_selector_diff.passed if entity not in upserted_entities])

        try:
            await self.entities_state_applier.delete(entities_to_delete, UserAgentType.exporter)
        except Exception as e:
            logger.error(f"Failed to delete entities: {str(e)}")
