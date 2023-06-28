from typing import Any

from pydantic import BaseModel
from pydantic.fields import Field


class Entity(BaseModel):
    identifier: str
    blueprint: str
    title: str | None
    team: str | list[str] = []
    properties: dict[str, Any] = {}
    relations: dict[str, str] = {}


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
