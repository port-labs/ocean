"""Pydantic models used only for JSON Schema export (CLI / UI), not for runtime parsing."""

from __future__ import annotations

from functools import lru_cache
from typing import Type

from pydantic import BaseModel


@lru_cache(maxsize=256)
def selector_model_for_schema_export(selector_cls: Type[BaseModel]) -> Type[BaseModel]:
    """Return a subclass of *selector_cls* used only for JSON Schema export.
    The integration's real selector in ``models.py`` is left unchanged;
    runtime config parsing still uses that class.
    """
    if not isinstance(selector_cls, type) or not issubclass(selector_cls, BaseModel):
        raise TypeError(f"Expected a Pydantic BaseModel subclass, got {selector_cls!r}")

    class Config:
        extra = "forbid"

    return type(
        f"{selector_cls.__name__}SchemaExport",
        (selector_cls,),
        {"Config": Config},
    )
