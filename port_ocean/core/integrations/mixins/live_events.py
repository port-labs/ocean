import asyncio
from typing import Set
from loguru import logger
from port_ocean.clients.port.types import UserAgentType
from port_ocean.context.event import EventType, event_context
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventData
from port_ocean.core.integrations.mixins.handler import HandlerMixin
from port_ocean.core.models import Entity
from port_ocean.core.ocean_types import RAW_ITEM, CalculationResult
from port_ocean.context.ocean import ocean
from port_ocean.context.event import event


class LiveEventsMixin(HandlerMixin):

    async def process_data(self, webhookEventDatas: list[WebhookEventData]) -> None:
        """Process the webhook event data collected from multiple processors.

        Args:
            webhookEventDatas: List of WebhookEventData objects to process
        """
        # async with event_context(
        #     EventType.LIVE_EVENT,
        #     trigger_type="machine",
        # ):
        for webhookEventData in webhookEventDatas:
            resource_mappings = await self._get_live_event_resources(
                webhookEventData.kind
            )
            for raw_item in webhookEventData.data:
                await self._export_single_resource(resource_mappings, raw_item)

    async def _calculate_raw(
        self,
        raw_data_and_matching_resource_config: list[
            tuple[ResourceConfig, list[RAW_ITEM]]
        ],
        parse_all: bool = False,
        send_raw_data_examples_amount: int = 0,
    ) -> list[CalculationResult]:
        return await asyncio.gather(
            *(
                self.entity_processor.parse_items(
                    mapping, raw_data, parse_all, send_raw_data_examples_amount
                )
                for mapping, raw_data in raw_data_and_matching_resource_config
            )
        )

    async def _get_live_event_resources(self, kind: str) -> list[ResourceConfig]:
        try:
            # app_config = await self.port_app_config_handler.get_port_app_config(
            #     use_cache=False
            # )
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

    async def _export(self, resource_mapping: ResourceConfig, raw_item: RAW_ITEM) -> tuple[bool, list[str]]:
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

            upsertedEntities = await self.entities_state_applier.upsert(calculation_results.    entity_selector_diff.passed, UserAgentType.exporter)
            return True, upsertedEntities

        except Exception as e:
            logger.error(f"Error exporting resource {resource_mapping.kind}: {str(e)}")
            return False, []

    async def _is_entity_exists(self, entity: Entity) -> bool:
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

    def _all_entities_filtered_out_at_exort(self, exportSucceded: bool, exportedEntities: list[Entity]) -> bool:
        return exportSucceded and len(exportedEntities) == 0

    async def _get_entities_to_delete(self, resource_mapping: ResourceConfig, raw_item: RAW_ITEM) -> list[Entity]:
        calculation_results = await self.entity_processor.parse_items(
                    resource_mapping, [raw_item], parse_all=True, send_raw_data_examples_amount=0
                )
        if len(calculation_results.entity_selector_diff.failed) == 1 and await self._is_entity_exists(calculation_results.entity_selector_diff.failed[0]):
            return calculation_results.entity_selector_diff.failed
        return []

    async def _export_single_resource(self, resource_mappings: list[ResourceConfig], raw_item: RAW_ITEM) -> None:
        entitiesToDelete: list[Entity] = []
        blueprintsToKeep: Set[str] = set()

        logger.info(f"Exporting single resource: {raw_item}")
        for resource_mapping in resource_mappings:
            exportSucceded, exportedEntities = await self._export(resource_mapping, raw_item)
            if self._all_entities_filtered_out_at_exort(exportSucceded, exportedEntities):
                entitiesToDelete.extend(await self._get_entities_to_delete(resource_mapping, raw_item))
            else:
                for entity in exportedEntities:
                    blueprintsToKeep.add(entity.blueprint)

        entitiesToDeleteFilteredByKeptBlueprints = [entity for entity in entitiesToDelete if entity.blueprint not in blueprintsToKeep]

        logger.info(f"Deleting entities after filtering out the bluepprint entities to keep",
                    deleted_entities_count=len(entitiesToDeleteFilteredByKeptBlueprints))
        try:
            if entitiesToDeleteFilteredByKeptBlueprints:
                await self.entities_state_applier.delete(entitiesToDeleteFilteredByKeptBlueprints)
        except Exception as e:
            logger.error(f"Failed to delete entities: {str(e)}")
