from typing import Any, Dict

from pydantic import BaseModel


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
