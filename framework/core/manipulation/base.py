from abc import abstractmethod
from dataclasses import dataclass, field
from typing import List, TypeVar, Union, Generic

from framework.core.integrations.base import Change
from framework.models.port import Entity, Blueprint
from framework.models.port_app_config import ResourceConfig

T = TypeVar('T', bound=Union[Blueprint, Entity])


@dataclass
class EntitiesDiff(Generic[T]):
    deleted: List[T] = field(default_factory=list)
    modified: List[T] = field(default_factory=list)
    created: List[T] = field(default_factory=list)

    def extend(self, created: List[T], modified: List[T], deleted: List[T]):
        self.created.extend(created)
        self.modified.extend(modified)
        self.deleted.extend(deleted)


class BaseManipulation:
    @abstractmethod
    def get_entities_diff(self, mapping: ResourceConfig, raw_data: List[Change]) -> EntitiesDiff:
        pass
