from __future__ import annotations

from typing import Any

from pydantic.v1 import BaseModel


class FactoryModel(BaseModel):
    """Base for Factory Public API payloads.

    ``extra = allow`` keeps unknown fields so Port mappings stay forward-compatible.
    ``dict(by_alias=True)`` restores the API's camelCase shape for Ocean RAW_ITEMs.
    """

    class Config:
        extra = "allow"
        allow_population_by_field_name = True
        frozen = True

    def to_raw_item(self) -> dict[str, Any]:
        return self.dict(by_alias=True)
