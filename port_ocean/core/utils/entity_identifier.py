import json
from typing import Any

from pydantic.v1 import BaseModel


def identifier_to_dict(identifier: Any) -> dict[str, Any] | None:
    if isinstance(identifier, BaseModel):
        identifier = identifier.dict()

    return identifier if isinstance(identifier, dict) else None


def normalize_identifier(identifier: Any) -> str:
    identifier_dict = identifier_to_dict(identifier)
    if identifier_dict is not None:
        return json.dumps(identifier_dict, sort_keys=True)

    return str(identifier)
