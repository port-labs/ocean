from abc import abstractmethod
from dataclasses import dataclass, field
from typing import List

from port_ocean.core.base import BaseWithContext
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.models import Entity
from port_ocean.types import EntityRawDiff, EntityDiff


@dataclass
class EntityPortDiff:
    deleted: List[Entity] = field(default_factory=list)
    modified: List[Entity] = field(default_factory=list)
    created: List[Entity] = field(default_factory=list)


class BaseManipulation(BaseWithContext):
    @abstractmethod
    async def parse_items(
        self, mapping: ResourceConfig, raw_data: List[EntityRawDiff]
    ) -> EntityDiff:
        pass
