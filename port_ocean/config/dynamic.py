import json
from typing import Type, Any, Optional, Callable

from humps import decamelize
from pydantic import (
    BaseModel,
    AnyUrl,
    create_model,
    Extra,
    field_validator,
    TypeAdapter,
)


class Configuration(BaseModel, extra=Extra.allow):
    name: str
    type: str
    required: bool = False
    default: Optional[Any] = None


def dict_parse_validator(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass
    return value


def _create_validators(
    fields: dict[str, tuple[Any, Any]]
) -> dict[str, Callable[..., Any]]:
    validators = {}
    for field_name, (field_type, default) in fields.items():
        if issubclass(field_type, dict) or issubclass(field_type, list):
            validators[field_name] = classmethod(
                field_validator(field_name, mode="before")(dict_parse_validator)  # type: ignore
            )
    return validators


def default_config_factory(configurations: Any) -> Type[BaseModel]:
    configurations = TypeAdapter(list[Configuration]).validate_python(configurations)
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
            case _:
                raise ValueError(f"Unknown type: {config.type}")

        default = ... if config.required else None
        if config.default is not None:
            default = TypeAdapter(field_type).validate_python(config.default)
        fields[decamelize(config.name)] = (
            field_type,
            default,
        )

    dynamic_model = create_model(
        "Config",
        __validators__=_create_validators(fields),
        fields=fields,
    )
    return dynamic_model
