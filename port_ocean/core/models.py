from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pydantic import BaseModel
from pydantic.fields import Field


class Runtime(Enum):
    Saas = "Saas"
    OnPrem = "OnPrem"


class Entity(BaseModel):
    identifier: Any
    blueprint: Any
    title: Any
    team: str | None | list[Any] = []
    properties: dict[str, Any] = {}
    relations: dict[str, Any] = {}

    @property
    def is_using_search_identifier(self) -> bool:
        return isinstance(self.identifier, dict)


class BlueprintRelation(BaseModel):
    many: bool
    required: bool
    target: str
    title: str | None


class Blueprint(BaseModel):
    identifier: str
    title: str | None
    team: str | None
    properties_schema: dict[str, Any] = Field(alias="schema")
    relations: dict[str, BlueprintRelation]


class Migration(BaseModel):
    id: str
    actor: str
    sourceBlueprint: str
    mapping: dict[str, Any]
    status: str


@dataclass
class EntityPortDiff:
    """Represents the differences between entities for porting.

    This class holds the lists of deleted, modified, and created entities as part
    of the porting process.
    """

    deleted: list[Entity] = field(default_factory=list)
    modified: list[Entity] = field(default_factory=list)
    created: list[Entity] = field(default_factory=list)
