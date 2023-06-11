from pydantic import BaseModel


class Entity(BaseModel):
    identifier: str
    blueprint: str
    title: str | None
    team: str | None
    properties: dict
    relations: dict


class Blueprint(BaseModel):
    identifier: str
    title: str | None
    team: str | None
    properties: dict
    relations: dict
