from typing import Type, Any

from pydantic import BaseModel, AnyUrl, create_model, Extra, parse_obj_as


class Configuration(BaseModel, extra=Extra.allow):
    name: str
    type: str
    required: bool = False


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

        fields[config.name] = (
            field_type,
            ... if config.required else None,
        )

    return create_model("Config", **fields)  # type: ignore
