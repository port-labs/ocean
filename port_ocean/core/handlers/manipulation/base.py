from abc import abstractmethod
from dataclasses import dataclass, field
from typing import List, TypeVar, Union, Generic, Tuple

from port_ocean.core.base import BaseWithContext
from port_ocean.models.diff import Change
from port_ocean.models.port import Entity, Blueprint
from port_ocean.models.port_app_config import ResourceConfig

T = TypeVar("T", bound=Union[Blueprint, Entity])


@dataclass
class PortObjectDiff(Generic[T]):
    deleted: List[T] = field(default_factory=list)
    modified: List[T] = field(default_factory=list)
    created: List[T] = field(default_factory=list)


def flatten_diff(changes: List[PortObjectDiff[T]]) -> PortObjectDiff[T]:
    result: Tuple[List[T], List[T], List[T]] = zip(  # type: ignore
        *((change.created, change.deleted, change.modified) for change in changes)
    )
    return PortObjectDiff[T](*result)


PortDiff = Tuple[PortObjectDiff[Entity], PortObjectDiff[Blueprint]]


class BaseManipulation(BaseWithContext):
    @abstractmethod
    def get_diff(self, mapping: ResourceConfig, raw_data: List[Change]) -> PortDiff:
        pass
