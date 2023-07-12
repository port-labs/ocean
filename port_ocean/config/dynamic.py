from typing import Type, Any

from pydantic import BaseModel, AnyUrl, create_model, Extra


class Spec(BaseModel):
    class Configurations(BaseModel, extra=Extra.allow):
        name: str
        type: str
        required: bool = False

    configurations: list[Configurations] = []


def default_config_factory(configurations: Any) -> Type[BaseModel]:
    spec: Spec = Spec.parse_obj(configurations)

    fields: dict[str, tuple[Any, Any]] = {}

    for config in spec.configurations:
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
