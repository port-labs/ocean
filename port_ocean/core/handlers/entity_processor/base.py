from abc import abstractmethod
from dataclasses import dataclass, field

from loguru import logger

from port_ocean.core.handlers.base import BaseHandler
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.models import Entity
from port_ocean.core.ocean_types import RawEntityDiff, EntityDiff


@dataclass
class EntityPortDiff:
    """Represents the differences between entities for porting.

    This class holds the lists of deleted, modified, and created entities as part
    of the porting process.
    """

    deleted: list[Entity] = field(default_factory=list)
    modified: list[Entity] = field(default_factory=list)
    created: list[Entity] = field(default_factory=list)


class BaseEntityProcessor(BaseHandler):
    """Abstract base class for processing and parsing entities.

    This class defines abstract methods for parsing raw entity data into entity diffs.

    Attributes:
        context (Any): The context to be used during entity processing.
    """

    @abstractmethod
    async def _parse_items(
        self, mapping: ResourceConfig, raw_data: RawEntityDiff
    ) -> EntityDiff:
        pass

    async def parse_items(
        self, mapping: ResourceConfig, raw_data: RawEntityDiff
    ) -> EntityDiff:
        """Public method to parse raw entity data and map it to an EntityDiff.

        Args:
            mapping (ResourceConfig): The configuration for entity mapping.
            raw_data (RawEntityDiff): The raw data to be parsed.

        Returns:
            EntityDiff: The parsed entity differences.
        """
        with logger.contextualize(kind=mapping.kind):
            return await self._parse_items(mapping, raw_data)
