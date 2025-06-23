from dataclasses import dataclass, field
from enum import Enum, StrEnum
from typing import Any, TypedDict

from pydantic import BaseModel
from pydantic.fields import Field


class CreatePortResourcesOrigin(StrEnum):
    Ocean = "Ocean"
    Port = "Port"


class ProcessExecutionMode(StrEnum):
    multi_process = "multi_process"
    single_process = "single_process"


class CachingStorageMode(StrEnum):
    disk = "disk"
    memory = "memory"


class Runtime(Enum):
    Saas = "Saas"
    OnPrem = "OnPrem"

    @property
    def is_saas_runtime(self) -> bool:
        return self in [Runtime.Saas]

    def is_installation_type_compatible(self, installation_type: str) -> bool:
        """
        Check if the installation type is compatible with the runtime

        if the runtime is Saas, the installation type should start with Saas
        else the installation type should be OnPrem
        """
        return (
            self.value == Runtime.Saas.value
            and installation_type.startswith(self.value)
        ) or installation_type == self.value


class PortAPIErrorMessage(Enum):
    NOT_FOUND = "not_found"


class Entity(BaseModel):
    identifier: Any
    icon: str | None
    blueprint: Any
    title: Any
    team: str | None | list[Any] | dict[str, Any] = []
    properties: dict[str, Any] = {}
    relations: dict[str, Any] = {}

    @property
    def is_using_search_identifier(self) -> bool:
        return isinstance(self.identifier, dict)

    @property
    def is_using_search_relation(self) -> bool:
        return any(
            isinstance(relation, dict) for relation in self.relations.values()
        ) or (
            self.team is not None and any(isinstance(team, dict) for team in self.team)
        )


class EntityBulkResult(TypedDict):
    identifier: str
    index: int
    created: bool


class EntityBulkError(TypedDict):
    identifier: str
    index: int
    statusCode: int
    error: str
    message: str


class BulkUpsertResponse(TypedDict):
    entities: list[EntityBulkResult]
    errors: list[EntityBulkError]


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
