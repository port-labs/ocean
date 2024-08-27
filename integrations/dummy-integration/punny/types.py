from pydantic import BaseModel
from enum import StrEnum


class Funny(StrEnum):
    YAAS = "YAAS"
    NOPE = "NOPE"


class PunCategory(BaseModel):
    id: str
    name: str


class Pun(BaseModel):
    id: str
    name: str
    funny: Funny
    score: int
    category: PunCategory
    text: str

    class Config:
        use_enum_values = True
