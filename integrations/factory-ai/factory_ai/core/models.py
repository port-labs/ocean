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


class FactoryListOptions(BaseModel):
    """Base for list-endpoint query options.

    Declare optional params with camelCase ``Field(alias=...)``. ``None`` and
    ``False`` are omitted; ``True`` becomes ``"true"``.
    """

    class Config:
        allow_population_by_field_name = True

    def to_query_params(self) -> dict[str, str]:
        params: dict[str, str] = {}
        for name, field in self.__fields__.items():
            value = getattr(self, name)
            if value is None or value is False:
                continue
            key = field.alias or name
            params[key] = "true" if value is True else str(value)
        return params
