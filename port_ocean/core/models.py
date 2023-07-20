from typing import Any, Type, TypeVar

from pydantic import BaseModel
from pydantic.fields import Field

Model = TypeVar("Model", bound="BaseModel")


class Entity(BaseModel):
    identifier: str
    blueprint: str
    title: str | None
    team: str | list[str] = []
    properties: dict[str, Any] = {}
    relations: dict[str, Any] = {}

    @classmethod
    def parse_obj(cls: Type["Model"], obj: dict[Any, Any]) -> "Model":
        obj["identifier"] = str(obj.get("identifier"))
        obj["blueprint"] = str(obj.get("blueprint"))
        if obj.get("team"):
            team = obj.get("team")
            obj["team"] = (
                [str(item) for item in team]
                if isinstance(team, list)
                else str(obj.get("team"))
            )

        for key, value in obj.get("relations", {}).items():
            if isinstance(value, list):
                obj["relations"][key] = [str(item) for item in value]
            else:
                obj["relations"][key] = str(value)
        return super(Entity, cls).parse_obj(obj)


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
