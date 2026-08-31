from __future__ import annotations

import importlib
import json
import types
from typing import Any, Literal, Type, Union, get_args, get_origin

from pydantic.v1 import BaseModel

from port_ocean.core.handlers.port_app_config.models import (
    CUSTOM_KIND,
    PortAppConfig,
    ProbePermissions,
    ResourceConfig,
    Selector,
)
from port_ocean.utils.misc import get_subclass_class_from_module


def validate_and_get_config_schema(
    config_class: Type[PortAppConfig],
) -> dict[str, Any]:
    """Validate config definitions and return UI schema (kinds + advancedConfig)."""
    _enforce_field_metadata(config_class)
    models = _get_resource_config_models(config_class)
    _validate_kind_discriminator(models)
    kinds = _build_kinds_mapping(models, config_class.allow_custom_kinds)
    return {
        "kinds": kinds,
        "advancedConfig": _get_advanced_config(config_class),
    }


def get_port_app_config_kinds(config_class: Type[PortAppConfig]) -> list[str]:
    """Return literal resource kind values declared on a PortAppConfig class."""
    kinds = _build_kinds_mapping(
        _get_resource_config_models(config_class),
        config_class.allow_custom_kinds,
    )
    return sorted(kind for kind in kinds if kind != CUSTOM_KIND)


def get_kind_probe_permissions(
    config_class: Type[PortAppConfig],
    *,
    permission_key: str | None = None,
) -> dict[str, tuple[str, ...]]:
    """Return probe permission requirements keyed by resource kind.

    Resource configs may declare ``probe_permissions`` as either a single tuple
    (one permission namespace) or a dict keyed by auth mode / namespace.
    When a dict is used, *permission_key* selects the active namespace.
    """
    kind_permissions: dict[str, tuple[str, ...]] = {}
    for model in _get_resource_config_models(config_class):
        if not (isinstance(model, type) and issubclass(model, ResourceConfig)):
            continue

        kind_field = model.__fields__.get("kind")
        if kind_field is None:
            continue

        kind_value = _resolve_kind_value(
            kind_field, model.__name__, config_class.allow_custom_kinds
        )
        if kind_value is None or kind_value == CUSTOM_KIND:
            continue

        permissions = _resolve_probe_permissions_for_model(model, permission_key)
        if permissions:
            kind_permissions[kind_value] = permissions

    return kind_permissions


def _resolve_probe_permissions_for_model(
    model: type,
    permission_key: str | None,
) -> tuple[str, ...] | None:
    permissions: ProbePermissions | None = getattr(model, "probe_permissions", None)
    if permissions is None:
        return None
    if isinstance(permissions, tuple):
        return permissions
    if isinstance(permissions, dict):
        if permission_key is None:
            raise ValueError(
                f"{model.__name__}.probe_permissions is a dict; "
                "permission_key is required"
            )
        resolved = permissions.get(permission_key)
        return resolved if resolved else None
    raise TypeError(
        f"{model.__name__}.probe_permissions must be a tuple or dict, "
        f"got {type(permissions).__name__}"
    )


def _is_model(annotation: Any, model: type) -> bool:
    try:
        return isinstance(annotation, type) and issubclass(annotation, model)
    except TypeError:
        return False


def _is_resources_or_selector_type(annotation: Any) -> bool:
    """True for ``Selector`` or ``list[ResourceConfig | …]`` (type-narrowing slots)."""
    if _is_model(annotation, Selector):
        return True
    if get_origin(annotation) is not list:
        return False
    args = get_args(annotation)
    if not args:
        return False
    members = _unwrap_union(args[0])
    return bool(members) and all(_is_model(m, ResourceConfig) for m in members)


def _require_title_and_description(name: str, cls: type, info: Any) -> None:
    if info.title is None:
        raise TypeError(f"Field '{name}' in '{cls.__name__}' must have a 'title'")
    if info.description is None:
        raise TypeError(f"Field '{name}' in '{cls.__name__}' must have a 'description'")


def _nested_types(annotation: Any) -> list[type]:
    if get_origin(annotation) is list:
        args = get_args(annotation)
        annotation = args[0] if args else annotation
    return [t for t in _unwrap_union(annotation) if isinstance(t, type)]


def _enforce_field_metadata(config_class: Type[PortAppConfig]) -> None:
    """Require title/description on every field in the PortAppConfig tree.

    ``Selector`` and ``list[ResourceConfig]`` may omit Field metadata so
    integrations can narrow those types. Nested fields with the same names
    are still checked.
    """
    seen: set[type] = set()

    def check(cls: type) -> None:
        if cls in seen:
            return
        try:
            if not issubclass(cls, BaseModel):
                return
        except TypeError:
            return
        seen.add(cls)

        for name, field in cls.__fields__.items():
            if not _is_resources_or_selector_type(field.outer_type_):
                _require_title_and_description(name, cls, field.field_info)
            for nested in _nested_types(field.outer_type_):
                check(nested)

    check(config_class)


def _validate_kind_discriminator(models: list[type]) -> None:
    """Ensure ``kind`` is a unique discriminator across the resources union.

    Raises :class:`TypeError` on duplicate ``Literal`` kinds or more than one
    ``kind: str`` (custom-kind) slot.
    """
    seen_literal_kinds: dict[str, str] = {}
    custom_kind_model: str | None = None

    for model in models:
        if not (isinstance(model, type) and issubclass(model, ResourceConfig)):
            continue

        kind_field = model.__fields__.get("kind")
        if kind_field is None:
            raise TypeError(f"{model.__name__} is missing the required 'kind' field")

        try:
            kind_value = _resolve_kind_value(
                kind_field, model.__name__, allow_custom_kinds=True
            )
        except ValueError as e:
            raise TypeError(str(e)) from e

        if kind_value == CUSTOM_KIND:
            if custom_kind_model is not None:
                raise TypeError(
                    f"Multiple custom kind definitions detected: both "
                    f"{custom_kind_model} and {model.__name__} define "
                    f"'kind: str'. Only one ResourceConfig with "
                    f"'kind: str' is allowed"
                )
            custom_kind_model = model.__name__
            continue

        if kind_value in seen_literal_kinds:
            raise TypeError(
                f"Duplicate kind '{kind_value}': both "
                f"{seen_literal_kinds[kind_value]} and {model.__name__} "
                f"define the same kind value. "
                f"'kind' must be a unique discriminator across the "
                f"resources union"
            )
        seen_literal_kinds[kind_value] = model.__name__


def _get_resource_config_models(config_class: Type[PortAppConfig]) -> list[type]:
    """Return ``ResourceConfig`` types from the ``resources`` field annotation.

    Handles both ``list[SingleModel]`` and ``list[Union[A | B | …]]``.
    """
    resources_field = config_class.__fields__.get("resources")
    if resources_field is None:
        return []

    list_args = get_args(resources_field.outer_type_)
    if not list_args:
        return []

    return _unwrap_union(list_args[0])


def _unwrap_union(annotation: Any) -> list[type]:
    """Unwrap a ``Union`` (or Python 3.10+ ``X | Y``) into member types."""
    origin = get_origin(annotation)
    if origin is Union:
        return list(get_args(annotation))
    if hasattr(types, "UnionType") and isinstance(annotation, types.UnionType):
        return list(get_args(annotation))
    return [annotation]


def _get_advanced_config(config_class: Type[PortAppConfig]) -> dict[str, Any]:
    """Root PortAppConfig field metadata (everything except ``resources``)."""
    schema = config_class.schema()
    return {k: v for k, v in schema.get("properties", {}).items() if k != "resources"}


def _get_selector_schema(selector_type: Any, model: type) -> dict[str, Any]:
    """JSON schema for the selector type, or from model's module, or base Selector."""
    if isinstance(selector_type, type) and hasattr(selector_type, "schema"):
        return selector_type.schema()
    selector_class = get_subclass_class_from_module(
        importlib.import_module(model.__module__), Selector
    )
    if selector_class is not None:
        return selector_class.schema()
    return Selector.schema()


def _build_kinds_mapping(
    models: list[type],
    allow_custom_kinds: bool,
) -> dict[str, dict[str, Any]]:
    """Walk *models*, validate each ``kind``, and build the kinds mapping."""
    kinds: dict[str, dict[str, Any]] = {}

    for model in models:
        if not (isinstance(model, type) and issubclass(model, ResourceConfig)):
            continue

        kind_field = model.__fields__.get("kind")
        if kind_field is None:
            raise ValueError(f"{model.__name__} is missing the required 'kind' field")

        kind_value = _resolve_kind_value(kind_field, model.__name__, allow_custom_kinds)
        if kind_value is None:
            raise ValueError(f"{model.__name__}: could not resolve kind value")
        if kind_value != CUSTOM_KIND and kind_value in kinds:
            raise ValueError(
                f"Duplicate kind '{kind_value}' found in resource config models"
            )

        kind_entry = _field_info_to_dict(kind_field.field_info)

        selector_field = model.__fields__.get("selector")
        if selector_field is not None:
            kind_entry["selectors"] = _get_selector_schema(
                selector_field.outer_type_, model
            )

        kinds[kind_value] = kind_entry

    return kinds


def _is_json_safe(value: Any) -> bool:
    try:
        json.dumps(value)
        return True
    except (TypeError, ValueError, OverflowError):
        return False


def _field_info_to_dict(field_info: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for attr_name, attr_value in field_info.__repr_args__():
        if attr_name is None:
            continue
        # Flatten Pydantic's "extra" kwargs instead of nesting under "extra".
        if attr_name == "extra" and isinstance(attr_value, dict):
            result.update({k: v for k, v in attr_value.items() if _is_json_safe(v)})
        elif _is_json_safe(attr_value):
            result[attr_name] = attr_value
    return result


def _resolve_kind_value(
    kind_field: Any,
    model_name: str,
    allow_custom_kinds: bool,
) -> str:
    """Normalise a model's ``kind`` annotation.

    * ``Literal["x"]`` → ``"x"``
    * ``str`` (when allowed) → ``"__custom__"``
    * otherwise → raises ``ValueError``
    """
    kind_type = kind_field.outer_type_

    if get_origin(kind_type) is Literal:
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
                f"{model_name}: custom kinds are not allowed when "
                f"allow_custom_kinds is False"
            )
        return CUSTOM_KIND

    raise ValueError(
        f"{model_name}: kind must be Literal['value'] or str "
        f"(when allow_custom_kinds=True), got {kind_type}"
    )
