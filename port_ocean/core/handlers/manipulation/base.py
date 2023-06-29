from abc import abstractmethod
from dataclasses import dataclass, field

from port_ocean.core.base import BaseWithContext
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.models import Entity
from port_ocean.core.types import RawEntityDiff, EntityDiff


@dataclass
class EntityPortDiff:
    deleted: list[Entity] = field(default_factory=list)
    modified: list[Entity] = field(default_factory=list)
    created: list[Entity] = field(default_factory=list)


class BaseManipulation(BaseWithContext):
    @abstractmethod
    async def parse_items(
        self, mapping: ResourceConfig, raw_data: RawEntityDiff
    ) -> EntityDiff:
        pass
