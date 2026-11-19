from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class FactoryModel(BaseModel):
    """Base for Factory Public API payloads.

    ``extra="allow"`` keeps unknown fields so Port mappings stay forward-compatible.
    ``model_dump(by_alias=True, exclude_none=True)`` restores the API's camelCase
    shape and drops absent optional fields so JQ does not see invented nulls.
    """

    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
        frozen=True,
    )

    def to_raw_item(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_none=True)


class FactoryListOptions(BaseModel):
    """Base for list-endpoint query options.

    Declare optional params with camelCase ``Field(alias=...)``. Serialization
    uses pydantic ``model_dump(by_alias=True, exclude_none=True)`` so aliases and
    ``None`` omission come from the model config; booleans stay intentional
    (``False`` → ``"false"``, ``True`` → ``"true"``).
    """

    model_config = ConfigDict(populate_by_name=True)

    def to_query_params(self) -> dict[str, str]:
        raw = self.model_dump(by_alias=True, exclude_none=True)
        return {
            key: str(value).lower() if isinstance(value, bool) else str(value)
            for key, value in raw.items()
        }
