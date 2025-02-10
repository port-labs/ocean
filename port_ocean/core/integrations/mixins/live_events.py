import asyncio
from typing import Any, Dict
from loguru import logger
from port_ocean.clients.port.types import UserAgentType
from port_ocean.context import ocean
from port_ocean.context.event import EventType, event_context
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.integrations.mixins.events import EventsMixin
from port_ocean.core.integrations.mixins.handler import HandlerMixin
from port_ocean.core.ocean_types import RAW_ITEM, CalculationResult


class LiveEventsMixin(HandlerMixin, EventsMixin):
    """Mixin class for live events.

    This mixin class provides methods and properties for handling live events.
    """

    def __init__(self) -> None:
        HandlerMixin.__init__(self)
        EventsMixin.__init__(self)

    async def _get_live_event_resources(self, kind: str) -> list[ResourceConfig]:
        try:
            app_config = await self.port_app_config_handler.get_port_app_config(
                use_cache=False
            )
            logger.info(f"process data will use the following mappings: {app_config.dict()}")

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

    async def _get_entity_deletion_threshold(self) -> float:
        app_config = await self.port_app_config_handler.get_port_app_config(
            use_cache=True
        )
        return app_config.entity_deletion_threshold

    async def _calculate_raw(
        self,
        raw_data_and_matching_resource_config: list[tuple[ResourceConfig, list[RAW_ITEM]]],
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

    async def on_live_event(self, kind: str, event_data: list[RAW_ITEM], user_agent_type: UserAgentType = UserAgentType.exporter,) -> None:
        logger.info("Starting to process data for kind: {kind}")
        async with event_context(
            EventType.LIVE_EVENT,
            trigger_type="machine",
        ):
            logger.info("starting to process live event")

            resource_mappings = await self._get_live_event_resources(kind)

            if not resource_mappings:
                logger.warning(f"No resource mappings found for kind: {kind}")
                return

            generated_entities = []
            for resource_mapping in resource_mappings:
                logger.info(f"Processing data for resource: {resource_mapping.dict()}")
                calculation_results = await self._calculate_raw(
                    [(resource_mapping, event_data)]
                )
                modified_objects = await self.entities_state_applier.upsert(
                    calculation_results[0].entity_selector_diff.passed, user_agent_type
                    )
                generated_entities.extend(modified_objects)

            entities_at_port = await ocean.port_client.search_entities(
                        user_agent_type
                    )
            await self.entities_state_applier.delete_diff(
                {"before": entities_at_port, "after": generated_entities},
                user_agent_type, await self._get_entity_deletion_threshold()
            )
