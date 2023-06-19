from abc import abstractmethod
from dataclasses import dataclass, field
from typing import List, TypeVar, Union, Generic, Tuple

from port_ocean.core.base import BaseWithContext
from port_ocean.core.models import Entity, Blueprint
from port_ocean.types import RawObjectDiff
from port_ocean.core.handlers.port_app_config.models import ResourceConfig

T = TypeVar("T", bound=Union[Blueprint, Entity])


@dataclass
class PortObjectDiff(Generic[T]):
    deleted: List[T] = field(default_factory=list)
    modified: List[T] = field(default_factory=list)
    created: List[T] = field(default_factory=list)


def flatten_diff(changes: List[PortObjectDiff[T]]) -> PortObjectDiff[T]:
    unpacked_changes = (
        (change.deleted, change.modified, change.created) for change in changes
    )
    deleted, modified, created = tuple(  # type: ignore
        ([sum(items, []) for items in zip(*unpacked_changes)] or [[], [], []])
    )
    return PortObjectDiff[T](deleted, modified, created)


PortDiff = Tuple[PortObjectDiff[Entity], PortObjectDiff[Blueprint]]


class BaseManipulation(BaseWithContext):
    @abstractmethod
    async def get_diff(
        self, mapping: ResourceConfig, raw_data: List[RawObjectDiff]
    ) -> PortDiff:
        pass
