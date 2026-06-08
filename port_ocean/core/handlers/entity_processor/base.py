from abc import abstractmethod

from loguru import logger
from port_ocean.core.handlers.base import BaseHandler
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.ocean_types import (
    RAW_ITEM,
    CalculationResult,
    EntitySelectorDiff,
)


class BaseEntityProcessor(BaseHandler):
    """Abstract base class for processing and parsing entities.

    This class defines abstract methods for parsing raw entity data into entity diffs.

    Attributes:
        context (Any): The context to be used during entity processing.
    """

    @abstractmethod
    async def _parse_items(
        self,
        mapping: ResourceConfig,
        raw_data: list[RAW_ITEM],
        parse_all: bool = False,
    ) -> CalculationResult:
        pass

    async def parse_items(
        self,
        mapping: ResourceConfig,
        raw_data: list[RAW_ITEM],
        parse_all: bool = False,
    ) -> list[CalculationResult]:
        """Public method to parse raw entity data and map it to an EntityDiff.

        Args:
            mapping (ResourceConfig): The configuration for entity mapping.
            raw_data (list[RawEntity]): The raw data to be parsed.
            parse_all (bool): Whether to parse all data or just data that passed the selector.

        Returns:
            EntityDiff: The parsed entity differences.
        """
        with logger.contextualize(kind=mapping.kind, resource_kind=mapping.kind):
            if not raw_data:
                return [CalculationResult(EntitySelectorDiff([], []), [])]

            primary_items: list[RAW_ITEM] = []
            secondary_items: dict[str, list[RAW_ITEM]] = {}
            for item in raw_data:
                kind = item.get("_portOceanKind", mapping.kind)
                if kind == mapping.kind:
                    primary_items.append(item)
                else:
                    secondary_items[kind] = secondary_items.get(kind, []) + [item]

            parsed_items = [await self._parse_items(mapping, primary_items, parse_all)]
            if secondary_items:
                config = (
                    await self.context.app.integration.port_app_config_handler.get_port_app_config()
                )
                for secondary_item_type, secondary_items in secondary_items.items():
                    secondary_mapping = next(
                        resource
                        for resource in config.resources
                        if resource.kind == secondary_item_type
                    )
                    parsed_items.append(
                        await self._parse_items(
                            secondary_mapping, secondary_items, parse_all
                        )
                    )
            return parsed_items
