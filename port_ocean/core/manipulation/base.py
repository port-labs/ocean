from abc import abstractmethod
from dataclasses import dataclass, field
from typing import List, TypeVar, Union, Generic, Tuple

from port_ocean.config.integration import IntegrationConfiguration
from port_ocean.models.diff import Change
from port_ocean.models.port import Entity, Blueprint
from port_ocean.models.port_app_config import ResourceConfig

T = TypeVar("T", bound=Union[Blueprint, Entity])


@dataclass
class PortObjectDiff(Generic[T]):
    deleted: List[T] = field(default_factory=list)
    modified: List[T] = field(default_factory=list)
    created: List[T] = field(default_factory=list)


PortDiff = Tuple[PortObjectDiff[Entity], PortObjectDiff[Blueprint]]


class BaseManipulation:
    def __init__(self, config: IntegrationConfiguration):
        self.config = config

    @abstractmethod
    def get_diff(self, mapping: ResourceConfig, raw_data: List[Change]) -> PortDiff:
        pass
