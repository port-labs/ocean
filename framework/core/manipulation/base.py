from abc import abstractmethod
from typing import List


class EntitiesParsing:
    deleted: List[Entity]
    modified: List[Entity]
    created: List[Entity]


class BaseManipulation:
    @abstractmethod
    def __init__(self):
        pass

    @abstractmethod
    def parse_entities(self) -> EntitiesParsing:
        pass
