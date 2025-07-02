import json
from typing import Type, Any, Optional

from humps import decamelize
from pydantic import (
    BaseConfig,
    BaseModel,
    AnyUrl,
    create_model,
    Extra,
    parse_obj_as,
    validator,
)
from pydantic.fields import ModelField, Field

from port_ocean.config.base import BaseOceanModel


class NoTrailingSlashUrl(AnyUrl):
    @classmethod
    def validate(cls, value: Any, field: ModelField, config: BaseConfig) -> "AnyUrl":
        if value is not None:
            if isinstance(value, (bytes, bytearray)):
                try:
                    value = value.decode()
                except UnicodeDecodeError as exc:
                    raise ValueError("URL bytes must be valid UTF-8") from exc
            else:
                value = str(value)

            if value != "/":
                value = value.rstrip("/")
        return super().validate(value, field, config)


class Configuration(BaseModel, extra=Extra.allow):
    name: str
    type: str
    required: bool = False
    default: Optional[Any]
    sensitive: bool = False


def dynamic_parse(value: Any, field: ModelField) -> Any:
    should_json_load = issubclass(field.annotation, dict) or issubclass(
        field.annotation, list
    )
    if isinstance(value, str) and should_json_load:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass
    return value


def default_config_factory(configurations: Any) -> Type[BaseModel]:
    configurations = parse_obj_as(list[Configuration], configurations)
    fields: dict[str, tuple[Any, Any]] = {}

    for config in configurations:
        field_type: Type[Any]

        match config.type:
            case "object":
                field_type = dict
            case "url":
                field_type = NoTrailingSlashUrl
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

        default: Any = ... if config.required else None
        if config.default is not None:
            default = parse_obj_as(field_type, config.default)
        fields[decamelize(config.name)] = (
            field_type,
            Field(default, sensitive=config.sensitive),
        )

    dynamic_model = create_model(  # type: ignore
        __model_name="Config",
        __base__=BaseOceanModel,
        **fields,
        __validators__={"dynamic_parse": validator("*", pre=True)(dynamic_parse)},
    )
    return dynamic_model
