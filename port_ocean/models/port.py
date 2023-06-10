from dataclasses import dataclass


@dataclass
class Entity:
    identifier: str
    blueprint: str
    title: str | None
    team: str | None
    properties: dict
    relations: dict


@dataclass
class Blueprint:
    identifier: str
    title: str | None
    team: str | None
    properties: dict
    relations: dict
