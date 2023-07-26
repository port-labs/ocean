from typing import Type, Any, Optional

from humps import decamelize
from pydantic import BaseModel, AnyUrl, create_model, Extra, parse_obj_as


class Configuration(BaseModel, extra=Extra.allow):
    name: str
    type: str
    required: bool = False
    default: Optional[Any]


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
            case _:
                raise ValueError(f"Unknown type: {config.type}")

        default = ... if config.required else None
        if config.default is not None:
            default = parse_obj_as(field_type, config.default)
        fields[decamelize(config.name)] = (
            field_type,
            default,
        )

    return create_model("Config", **fields)  # type: ignore
