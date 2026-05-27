from datetime import datetime
from typing import AsyncGenerator
import uuid

from loguru import logger
from port_ocean.clients.port.types import UserAgentType
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventRawResults
from port_ocean.core.integrations.mixins.handler import HandlerMixin
from port_ocean.core.integrations.mixins.utils import handle_items_to_parse, is_dsp_mode_enabled, is_lakehouse_data_enabled
from port_ocean.core.models import Entity, LakehouseDataEntry, LakehouseDataEntryBatch, LakehouseDataEntryMetadata, LakehouseOperation, LakehouseEventType
from port_ocean.core.ocean_types import RAW_ITEM
from port_ocean.context.ocean import ocean



class LiveEventsMixin(HandlerMixin):

    async def sync_raw_results(self, webhook_events_raw_result: list[WebhookEventRawResults]) -> None:
        """Process the webhook event raw results collected from multiple processors and export it.

        Args:
            webhook_events_raw_result: List of WebhookEventRawResults objects to process
        """
        if await is_lakehouse_data_enabled():
            await self._send_webhook_raw_data_to_lakehouse(webhook_events_raw_result)

        if await is_dsp_mode_enabled():
            logger.info("DSP mode active: skipping transform and load for live events")
            return

        entities_to_create, entities_to_delete = await self._parse_raw_event_results_to_entities(webhook_events_raw_result)

        if entities_to_create:
            await self.entities_state_applier.upsert(entities_to_create, UserAgentType.exporter)

        if entities_to_delete:
            await self._delete_entities(entities_to_delete)


    async def _expand_raw_item(
        self, raw_item: RAW_ITEM, resource: ResourceConfig
    ) -> AsyncGenerator[list[RAW_ITEM], None]:
        if resource.port.items_to_parse and not await is_dsp_mode_enabled():
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
                        resource, batch, parse_all=True
                    )
                    entities.extend(calculation_results.entity_selector_diff.passed)
                    entities_not_passed.extend(calculation_results.entity_selector_diff.failed)

            for raw_item in webhook_event_raw_result.deleted_raw_results:
                async for batch in self._expand_raw_item(raw_item, resource):
                    deletion_results = await self.entity_processor.parse_items(
                        resource, batch, parse_all=True
                    )
                    entities_to_delete.extend(deletion_results.entity_selector_diff.passed)

        entities_to_remove = []
        for entity in entities_to_delete + entities_not_passed:
            if (entity.blueprint, entity.identifier) not in [(entity.blueprint, entity.identifier) for entity in entities]:
                entities_to_remove.append(entity)

        logger.info(f"Found {len(entities_to_remove)} entities to remove {', '.join(f'{entity.blueprint}/{entity.identifier}' for entity in entities_to_remove)}")
        logger.info(f"Found {len(entities)} entities to upsert {', '.join(f'{entity.blueprint}/{entity.identifier}' for entity in entities)}")
        return entities, entities_to_remove

    async def _send_webhook_raw_data_to_lakehouse(
        self,
        webhook_events_raw_result: list[WebhookEventRawResults],
    ) -> None:
        """Send webhook raw data to lakehouse API with operation metadata.

        Sends ALL raw data before transformation to maintain audit trail,
        similar to how resync sends all raw data regardless of selector/mapping results.

        Both upserted and deleted items for the same webhook event are batched into a
        single POST request so the lakehouse can correlate them under one event ID.

        This is a best-effort operation - failures are logged but do not
        block webhook processing.

        Note: The caller should check if lakehouse is enabled before calling this method.

        Args:
            webhook_events_raw_result: List of WebhookEventRawResults objects to send to lakehouse
        """
        try:
            data_entries: list[LakehouseDataEntry] = []
            for webhook_event_raw_result in webhook_events_raw_result:
                event_id = webhook_event_raw_result._webhook_trace_id
                if not event_id:
                    logger.warning("Skipping lakehouse send - no trace_id available")
                    continue
                kind = webhook_event_raw_result.resource.kind

                resource_index = (
                    webhook_event_raw_result.resource_index
                    if webhook_event_raw_result.resource_index is not None
                    else 0
                )

                if webhook_event_raw_result.updated_raw_results:
                    data_entries.append(
                        LakehouseDataEntry(
                            request={},
                            response={},
                            items=webhook_event_raw_result.updated_raw_results,
                            metadata=LakehouseDataEntryMetadata(
                                operation=LakehouseOperation.UPSERT,
                                resource_index=resource_index,
                                extraction_timestamp=int(datetime.now().timestamp() * 1000),
                            ),
                        )
                    )
                if webhook_event_raw_result.deleted_raw_results:
                    data_entries.append(
                        LakehouseDataEntry(
                            request={},
                            response={},
                            items=webhook_event_raw_result.deleted_raw_results,
                            metadata=LakehouseDataEntryMetadata(
                                operation=LakehouseOperation.DELETE,
                                resource_index=resource_index,
                                extraction_timestamp=int(datetime.now().timestamp() * 1000),
                            ),
                        )
                    )

                logger.debug(
                    f"Sending {len(data_entries)} data entries to lakehouse",
                    event_id=event_id,
                    kind=kind,
                )
            if not data_entries:
                return
            try:
                event = LakehouseDataEntryBatch(
                    event_id=event_id,
                    type=LakehouseEventType.LIVE_EVENT.value,
                    kind=kind,
                    event_type=LakehouseEventType.LIVE_EVENT,
                    resync_start_time=webhook_event_raw_result.created_at,
                    extraction_timestamp=int(datetime.now().timestamp() * 1000),
                    data=data_entries,
                )
                event_id_str = event_id or str(uuid.uuid4())
                await ocean.port_client.post_integration_raw_data_batch(
                    event_id_str,
                    event,
                )
            except Exception as e:
                logger.warning(
                    f"Failed to send webhook raw data to lakehouse: {e}",
                    event_id=event_id,
                    kind=kind,
                )
        except Exception as e:
            logger.warning(
                f"Failed to send webhook raw data to lakehouse (best-effort operation): {e}"
            )

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
        """Delete entities that exist in Port.

        Args:
            entities: List of entities to delete
        """
        for entity in entities:
            if await self._does_entity_exists(entity):
                await self.entities_state_applier.delete([entity], UserAgentType.exporter)
