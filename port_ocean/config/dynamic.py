import json
from typing import Annotated, Any, Optional, Type

from humps import decamelize
from pydantic import (
    AnyUrl,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    TypeAdapter,
    create_model,
    field_validator,
)
from pydantic.fields import FieldInfo

from port_ocean.config.base import BaseOceanModel, sensitive_field


def _normalize_no_trailing_slash_url(value: Any) -> Any:
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
    TypeAdapter(AnyUrl).validate_python(value)
    return value


NoTrailingSlashUrl = Annotated[str, BeforeValidator(_normalize_no_trailing_slash_url)]


class Configuration(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    type: str
    required: bool = False
    default: Optional[Any] = None
    sensitive: bool = False


def dynamic_parse(value: Any, field: FieldInfo) -> Any:
    should_json_load = issubclass(field.annotation, dict) or issubclass(  # type: ignore[arg-type]
        field.annotation, list  # type: ignore[arg-type]
    )
    if isinstance(value, str) and should_json_load:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass
    return value


def default_config_factory(configurations: Any) -> Type[BaseModel]:
    configurations = TypeAdapter(list[Configuration]).validate_python(configurations)
    fields: dict[str, tuple[Any, Any]] = {}

    for config in configurations:
        field_type: Any

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
            default = TypeAdapter(field_type).validate_python(config.default)
        fields[decamelize(config.name)] = (
            field_type,
            sensitive_field(default=default) if config.sensitive else Field(default),
        )

    dynamic_model = create_model(  # type: ignore
        "Config",
        __base__=BaseOceanModel,
        **fields,
        __validators__={
            "dynamic_parse": field_validator("*", mode="before")(
                lambda cls, value, info: dynamic_parse(
                    value, cls.model_fields[info.field_name]
                )
            )
        },
    )
    return dynamic_model
