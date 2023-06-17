from typing import Dict, Any

from pydantic import BaseModel


class Entity(BaseModel):
    identifier: str
    blueprint: str
    title: str | None
    team: str | None
    properties: Dict[str, Any] = {}
    relations: Dict[str, str] = {}


class Blueprint(BaseModel):
    identifier: str
    title: str | None
    team: str | None
    properties: Dict[str, Any]
    relations: Dict[str, Any]
