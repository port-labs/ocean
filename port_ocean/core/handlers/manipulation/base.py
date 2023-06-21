from abc import abstractmethod
from dataclasses import dataclass, field
from typing import List, TypeVar, Union, Generic, Tuple

from port_ocean.core.base import BaseWithContext
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.models import Entity, Blueprint
from port_ocean.types import RawObjectDiff, ObjectDiff

T = TypeVar("T", bound=Union[Blueprint, Entity])


@dataclass
class PortDiff(Generic[T]):
    deleted: List[T] = field(default_factory=list)
    modified: List[T] = field(default_factory=list)
    created: List[T] = field(default_factory=list)


Diff = Tuple[ObjectDiff[Entity], ObjectDiff[Blueprint]]


class BaseManipulation(BaseWithContext):
    @abstractmethod
    async def parse_items(
        self, mapping: ResourceConfig, raw_data: List[RawObjectDiff]
    ) -> Diff:
        pass
