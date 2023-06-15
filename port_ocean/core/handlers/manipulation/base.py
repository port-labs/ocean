from abc import abstractmethod
from dataclasses import dataclass, field
from typing import List, TypeVar, Union, Generic, Tuple, Dict, Any

from pydantic import BaseModel

from port_ocean.core.base import BaseWithContext
from port_ocean.types import ObjectDiff
from port_ocean.core.handlers.port_app_config.models import ResourceConfig


class Entity(BaseModel):
    identifier: str
    blueprint: str
    title: str | None
    team: str | None
    properties: Dict[str, Any]
    relations: Dict[str, Any]

    def to_api_dict(self) -> Dict[str, Any]:
        return {
            "identifier": self.identifier,
            "title": self.title,
            "team": self.team,
            "properties": self.properties,
            "relations": self.relations,
        }


class Blueprint(BaseModel):
    identifier: str
    title: str | None
    team: str | None
    properties: Dict[str, Any]
    relations: Dict[str, Any]


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
    def get_diff(self, mapping: ResourceConfig, raw_data: List[ObjectDiff]) -> PortDiff:
        pass
