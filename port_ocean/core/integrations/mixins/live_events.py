import asyncio
from loguru import logger
from port_ocean.context.event import EventType, event_context
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventData
from port_ocean.core.integrations.mixins.handler import HandlerMixin
from port_ocean.core.models import Entity
from port_ocean.core.ocean_types import RAW_ITEM, CalculationResult


class LiveEventsMixin(HandlerMixin):

    async def process_data(self, webhookEventDatas: list[WebhookEventData]) -> None:
        """Process the webhook event data collected from multiple processors.

        Args:
            webhookEventDatas: List of WebhookEventData objects to process
        """
        # Filter out None values that might occur from failed processing
        createdEntities: list[Entity] = []
        deletedEntities: list[Entity] = []
        async with event_context(
            EventType.LIVE_EVENT,
            trigger_type="machine",
        ):
            for webhookEventData in webhookEventDatas:
                resource_mappings = await self._get_live_event_resources(
                    webhookEventData.kind
                )

                if not resource_mappings:
                    logger.warning(
                        f"No resource mappings found for kind: {webhookEventData.kind}"
                    )
                    continue

                if webhookEventData.update_data:
                    for resource_mapping in resource_mappings:
                        logger.info(
                            f"Processing data for resource: {resource_mapping.dict()}"
                        )
                        calculation_results = await self._calculate_raw(
                            [(resource_mapping, webhookEventData.update_data)]
                        )
                        createdEntities.extend(
                            calculation_results[0].entity_selector_diff.passed
                        )

                if webhookEventData.delete_data:
                    for resource_mapping in resource_mappings:
                        logger.info(
                            f"Processing delete data for resource: {resource_mapping.dict()}"
                        )
                        calculation_results = await self._calculate_raw(
                            [(resource_mapping, webhookEventData.delete_data)]
                        )
                        deletedEntities.extend(
                            calculation_results[0].entity_selector_diff.passed
                        )

            await self.entities_state_applier.upsert(  # add here better logic
                createdEntities
            )
            await self.entities_state_applier.delete(deletedEntities)

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
            app_config = await self.port_app_config_handler.get_port_app_config(
                use_cache=False
            )
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
