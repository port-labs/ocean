from typing import Dict, Any, List

from pydantic import BaseModel
from pydantic.fields import Field


class Entity(BaseModel):
    identifier: str
    blueprint: str
    title: str | None
    team: str | List[str] = []
    properties: Dict[str, Any] = {}
    relations: Dict[str, str] = {}


class BlueprintRelation(BaseModel):
    many: bool
    required: bool
    target: str
    title: str | None


class Blueprint(BaseModel):
    identifier: str
    title: str | None
    team: str | None
    properties_schema: Dict[str, Any] = Field(alias="schema")
    relations: Dict[str, BlueprintRelation]
