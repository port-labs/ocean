from loguru import logger
from port_ocean.clients.port.types import UserAgentType
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventRawResults
from port_ocean.core.integrations.mixins.handler import HandlerMixin
from port_ocean.core.models import Entity, IntegrationFeatureFlag, LakehouseOperation
from port_ocean.context.ocean import ocean



class LiveEventsMixin(HandlerMixin):

    async def sync_raw_results(self, webhook_events_raw_result: list[WebhookEventRawResults]) -> None:
        """Process the webhook event raw results collected from multiple processors and export it.

        Args:
            webhook_events_raw_result: List of WebhookEventRawResults objects to process
        """
        await self._send_webhook_raw_data_to_lakehouse(webhook_events_raw_result)

        entities_to_create, entities_to_delete = await self._parse_raw_event_results_to_entities(webhook_events_raw_result)

        if entities_to_create:
            await self.entities_state_applier.upsert(entities_to_create, UserAgentType.exporter)

        if entities_to_delete:
            await self._delete_entities(entities_to_delete)


    async def _parse_raw_event_results_to_entities(self, webhook_events_raw_result: list[WebhookEventRawResults]) -> tuple[list[Entity], list[Entity]]:
        """Parse the webhook event raw results and return a list of entities.

        Args:
            webhook_events_raw_result: List of WebhookEventRawResults objects to process
        """
        entities: list[Entity] = []
        entities_not_passed: list[Entity] = []
        entities_to_delete: list[Entity] = []
        for webhook_event_raw_result in webhook_events_raw_result:
            for raw_item in webhook_event_raw_result.updated_raw_results:
                calaculation_results = await self.entity_processor.parse_items(
                    webhook_event_raw_result.resource, [raw_item], parse_all=True, send_raw_data_examples_amount=0
                )
                entities.extend(calaculation_results.entity_selector_diff.passed)
                entities_not_passed.extend(calaculation_results.entity_selector_diff.failed)

            for raw_item in webhook_event_raw_result.deleted_raw_results:
                deletion_results = await self.entity_processor.parse_items(
                    webhook_event_raw_result.resource, [raw_item], parse_all=True, send_raw_data_examples_amount=0
                )
                entities_to_delete.extend(deletion_results.entity_selector_diff.passed)

        entities_to_remove = []
        for entity in entities_to_delete + entities_not_passed:
            if (entity.blueprint, entity.identifier) not in [(entity.blueprint, entity.identifier) for entity in entities]:
                entities_to_remove.append(entity)

        logger.info(f"Found {len(entities_to_remove)} entities to remove {', '.join(f'{entity.blueprint}/{entity.identifier}' for entity in entities_to_remove)}")
        logger.info(f"Found {len(entities)} entities to upsert {', '.join(f'{entity.blueprint}/{entity.identifier}' for entity in entities)}")
        return entities, entities_to_remove

    async def _lakehouse_data_enabled(self) -> bool:
        """Check if lakehouse data is enabled.

        Returns:
            bool: True if lakehouse data is enabled, False otherwise
        """
        flags = await ocean.port_client.get_organization_feature_flags()
        if (
            IntegrationFeatureFlag.LAKEHOUSE_ELIGIBLE in flags
            and ocean.config.lakehouse_enabled
        ):
            return True
        return False

    async def _send_webhook_raw_data_to_lakehouse(
        self,
        webhook_events_raw_result: list[WebhookEventRawResults],
    ) -> None:
        """Send webhook raw data to lakehouse API with operation metadata.

        Sends ALL raw data before transformation to maintain audit trail,
        similar to how resync sends all raw data regardless of selector/mapping results.

        Args:
            webhook_events_raw_result: List of WebhookEventRawResults objects to send to lakehouse
        """
        if not await self._lakehouse_data_enabled():
            return

        for webhook_event_raw_result in webhook_events_raw_result:
            event_id = webhook_event_raw_result._webhook_trace_id
            kind = webhook_event_raw_result.resource.kind

            if webhook_event_raw_result.updated_raw_results:
                logger.debug(
                    f"Sending {len(webhook_event_raw_result.updated_raw_results)} upserted raw items to lakehouse",
                    event_id=event_id,
                    kind=kind,
                )
                try:
                    await ocean.port_client.post_integration_raw_data(
                        webhook_event_raw_result.updated_raw_results,
                        event_id,
                        kind,
                        operation=LakehouseOperation.UPSERT,
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to send upserted webhook raw data to lakehouse: {e}",
                        event_id=event_id,
                        kind=kind,
                    )

            if webhook_event_raw_result.deleted_raw_results:
                logger.debug(
                    f"Sending {len(webhook_event_raw_result.deleted_raw_results)} deleted raw items to lakehouse",
                    event_id=event_id,
                    kind=kind,
                )
                try:
                    await ocean.port_client.post_integration_raw_data(
                        webhook_event_raw_result.deleted_raw_results,
                        event_id,
                        kind,
                        operation=LakehouseOperation.DELETE,
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to send deleted webhook raw data to lakehouse: {e}",
                        event_id=event_id,
                        kind=kind,
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
