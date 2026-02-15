from __future__ import annotations

import json
import types as _types
from typing import Any, Literal, Type, Union, get_args, get_origin

from pydantic import BaseModel

from port_ocean.core.handlers.port_app_config.models import CUSTOM_KIND, ResourceConfig


def validate_and_get_resource_kinds(
    config_class: Type[BaseModel],
    allow_custom_kinds: bool = False,
) -> dict[str, dict[str, Any]]:
    """Validate kind definitions and return a mapping of kind."""
    models = _get_resource_config_models(config_class)
    return _build_kinds_mapping(models, allow_custom_kinds)


def _get_resource_config_models(
    config_class: Type[BaseModel],
) -> list[type]:
    """Return the individual ``ResourceConfig`` model types from the
    ``resources`` field annotation.

    Handles both ``list[SingleModel]`` and ``list[Union[A | B | …]]``.
    """
    resources_field = config_class.__fields__.get("resources")
    if resources_field is None:
        return []

    annotation = resources_field.outer_type_
    list_args = get_args(annotation)
    if not list_args:
        return []

    inner = list_args[0]
    return _unwrap_union(inner)


def _unwrap_union(annotation: Any) -> list[type]:
    """Unwrap a ``Union`` (or Python 3.10+ ``X | Y``) into member types."""
    origin = get_origin(annotation)
    if origin is Union:
        return list[type](get_args(annotation))
    if hasattr(_types, "UnionType") and isinstance(annotation, _types.UnionType):
        return list[type](get_args(annotation))
    return [annotation]


def _build_kinds_mapping(
    models: list[type],
    allow_custom_kinds: bool,
) -> dict[str, dict[str, Any]]:
    """Walk *models*, validate each one's ``kind`` and build the mapping."""
    kinds: dict[str, dict[str, Any]] = {}

    for model in models:
        if not (isinstance(model, type) and issubclass(model, ResourceConfig)):
            continue

        kind_field = model.__fields__.get("kind")
        if kind_field is None:
            raise ValueError(f"{model.__name__} is missing the required 'kind' field")

        kind_value = _resolve_kind_value(kind_field, model.__name__, allow_custom_kinds)
        if kind_value != CUSTOM_KIND and kind_value in kinds:
            raise ValueError(
                f"Duplicate kind '{kind_value}' found in resource config models"
            )

        kinds[kind_value] = _field_info_to_dict(kind_field.field_info)

    return kinds


def _field_info_to_dict(field_info: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for attr_name, attr_value in field_info.__repr_args__():
        if attr_name is None:
            continue
        # The "extra" slot is Pydantic's catch-all for unknown kwargs passed
        # to Field().  Flatten its contents into the result instead of nesting
        # them under a redundant "extra" key.
        if attr_name == "extra" and isinstance(attr_value, dict):
            for k, v in attr_value.items():
                if _is_json_safe(json, v):
                    result[k] = v
        elif _is_json_safe(json, attr_value):
            result[attr_name] = attr_value
    return result


def _is_json_safe(json_mod: Any, value: Any) -> bool:
    """Return ``True`` if *value* survives ``json.dumps`` without error."""
    try:
        json_mod.dumps(value)
        return True
    except (TypeError, ValueError, OverflowError):
        return False


def _resolve_kind_value(
    kind_field: Any,
    model_name: str,
    allow_custom_kinds: bool,
) -> str | None:
    """Return the normalised kind string for a single model.

    * ``Literal["x"]`` → ``"x"``
    * ``str`` (when allowed) → ``"__custom__"``
    * ``str`` (when not allowed) → ``None`` (skip)
    * anything else → ``ValueError``
    """
    kind_type = kind_field.outer_type_
    kind_origin = get_origin(kind_type)

    if kind_origin is Literal:
        values = get_args(kind_type)
        if len(values) != 1:
            raise ValueError(
                f"{model_name}: kind Literal must contain exactly one string value, "
                f"got {len(values)}: {values}"
            )
        return str(values[0])

    if kind_type is str:
        if not allow_custom_kinds:
            raise ValueError(
                f"{model_name}: custom kinds are not allowed when allow_custom_kinds is False"
            )
        return CUSTOM_KIND

    raise ValueError(
        f"{model_name}: kind must be Literal['value'] or str "
        f"(when allow_custom_kinds=True), got {kind_type}"
    )
