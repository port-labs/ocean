"""Fill a full vendor model from the few fields a stub request sets."""

from __future__ import annotations

import types
from datetime import datetime, timezone
from typing import Any, Literal, Union, get_args, get_origin

from pydantic import BaseModel

_LITERAL = get_origin(Literal["example"])


def fill_model(model: type[BaseModel], values: dict[str, Any] | None) -> BaseModel:
    return model.model_validate(_fill(model, values or {}, ()))


def _fill(
    model: type[BaseModel],
    values: dict[str, Any],
    stack: tuple[type[BaseModel], ...],
) -> dict[str, Any] | None:
    if model in stack:
        return None
    provided = dict(values)
    consumed: set[str] = set()
    out: dict[str, Any] = {}
    for name, field in model.model_fields.items():
        key = (
            name
            if name in provided
            else field.alias if field.alias and field.alias in provided else None
        )
        if key is None:
            out[name] = _placeholder(field.annotation, stack + (model,))
            continue
        consumed.add(key)
        raw = provided[key]
        nested = _model_type(field.annotation)
        item_model = _list_model(field.annotation)
        if isinstance(raw, dict) and nested is not None:
            out[name] = _fill(nested, raw, stack + (model,))
        elif isinstance(raw, list) and item_model is not None:
            out[name] = [
                (
                    _fill(item_model, item, stack + (model,))
                    if isinstance(item, dict)
                    else item
                )
                for item in raw
            ]
        else:
            out[name] = raw
    for key, raw in provided.items():
        if key not in consumed:
            out[key] = raw
    return out


def _placeholder(annotation: Any, stack: tuple[type[BaseModel], ...]) -> Any:
    inner, _ = _strip_none(annotation)
    origin = get_origin(inner)
    if origin is _LITERAL:
        args = get_args(inner)
        return args[0] if args else "example"
    if origin is list:
        item = get_args(inner)[0] if get_args(inner) else Any
        return [_placeholder(item, stack)]
    if origin is dict:
        return {}
    model = _model_type(inner)
    if model is not None:
        if model in stack:
            return None
        return _fill(model, {}, stack)
    if inner is datetime:
        return datetime(2026, 1, 1, tzinfo=timezone.utc)
    if inner is str:
        return "example"
    if inner is int:
        return 1
    if inner is float:
        return 1.0
    if inner is bool:
        return False
    return "example"


def _strip_none(annotation: Any) -> tuple[Any, bool]:
    origin = get_origin(annotation)
    if origin is Union or origin is types.UnionType:
        args = [arg for arg in get_args(annotation) if arg is not type(None)]
        if len(args) == 1:
            return args[0], True
    return annotation, False


def _model_type(annotation: Any) -> type[BaseModel] | None:
    inner, _ = _strip_none(annotation)
    if isinstance(inner, type) and issubclass(inner, BaseModel):
        return inner
    return None


def _list_model(annotation: Any) -> type[BaseModel] | None:
    inner, _ = _strip_none(annotation)
    if get_origin(inner) is list:
        args = get_args(inner)
        if args:
            return _model_type(args[0])
    return None
