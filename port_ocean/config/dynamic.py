import json
from typing import Type, Any, Optional
from urllib.parse import urlparse, urlunparse

from humps import decamelize
from pydantic import BaseModel, AnyUrl, create_model, Extra, parse_obj_as, validator
from pydantic.fields import ModelField, Field

from port_ocean.config.base import BaseOceanModel


class Configuration(BaseModel, extra=Extra.allow):
    name: str
    type: str
    required: bool = False
    default: Optional[Any]
    sensitive: bool = False


def strip_url_trailing_slash(url: str) -> str:
    """Strip trailing slash from URL while preserving the rest of the URL structure."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    return urlunparse(parsed._replace(path=path))


def dynamic_parse(value: Any, field: ModelField) -> Any:
    should_json_load = issubclass(field.annotation, dict) or issubclass(
        field.annotation, list
    )
    if isinstance(value, str):
        if should_json_load:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                pass
        if field.annotation == AnyUrl:
            return strip_url_trailing_slash(value)
    return value


def _parse_obj_as(field_type: Type[Any], value: Any, is_url: bool = False) -> Any:
    parsed_value = parse_obj_as(field_type, value)
    if is_url and isinstance(parsed_value, str):
        parsed_value = strip_url_trailing_slash(parsed_value)
        parsed_value = parse_obj_as(field_type, parsed_value)
    return parsed_value


def default_config_factory(configurations: Any) -> Type[BaseModel]:
    configurations = parse_obj_as(list[Configuration], configurations)
    fields: dict[str, tuple[Any, Any]] = {}

    for config in configurations:
        field_type: Type[Any]

        match config.type:
            case "object":
                field_type = dict
            case "url":
                field_type = AnyUrl
            case "string":
                field_type = str
            case "integer":
                field_type = int
            case "boolean":
                field_type = bool
            case "array":
                field_type = list
            case _:
                raise ValueError(f"Unknown type: {config.type}")

        default = ... if config.required else None
        if config.default is not None:
            default = _parse_obj_as(
                field_type=field_type,
                value=config.default,
                is_url=(config.type == "url"),
            )
        fields[decamelize(config.name)] = (
            field_type,
            Field(default, sensitive=config.sensitive),
        )

    dynamic_model = create_model(
        __model_name="Config",
        __base__=BaseOceanModel,
        **fields,
        __validators__={
            "dynamic_parse": validator("*", pre=True, allow_reuse=True)(dynamic_parse)
        },
    )
    return dynamic_model
