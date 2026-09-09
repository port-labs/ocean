from typing import Any

from port_ocean.core.models import IntegrationRun
from pydantic.v1 import BaseModel, ValidationError

from linear.helpers.exceptions import MissingExecutionPropertyError


class LinearActionInput(BaseModel):
    class Config:
        extra = "ignore"

    @classmethod
    def from_execution_properties(cls, execution_properties: dict[str, Any]) -> Any:
        try:
            return cls.parse_obj(execution_properties)
        except ValidationError as error:
            raise MissingExecutionPropertyError(str(error)) from error


def require_non_empty_str(value: Any, field: Any) -> str:
    if value is None or (isinstance(value, str) and not str(value).strip()):
        raise ValueError(f"{field.name} is required")
    return str(value)


def require_property(
    run: IntegrationRun, name: str, *, title: str | None = None
) -> Any:
    value = run.execution_properties.get(name)
    if value is None or value == "":
        raise MissingExecutionPropertyError(f"{title or name} is required")
    return value


def optional_string(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def build_issue_create_input(properties: dict[str, Any]) -> dict[str, Any]:
    input_data: dict[str, Any] = {
        "title": require_property_from_dict(properties, "title"),
    }

    optional_fields = {
        "teamId": "teamId",
        "description": "description",
        "assigneeId": "assigneeId",
        "stateId": "stateId",
        "projectId": "projectId",
        "cycleId": "cycleId",
    }
    for input_key, property_key in optional_fields.items():
        if (value := properties.get(property_key)) is not None and value != "":
            input_data[input_key] = value

    if (priority := properties.get("priority")) is not None and priority != "":
        input_data["priority"] = _parse_priority(priority)

    label_ids = properties.get("labelIds")
    if isinstance(label_ids, list) and label_ids:
        input_data["labelIds"] = label_ids

    return input_data


def build_issue_update_input(properties: dict[str, Any]) -> dict[str, Any]:
    input_data: dict[str, Any] = {}
    optional_fields = {
        "title": "title",
        "description": "description",
        "assigneeId": "assigneeId",
        "stateId": "stateId",
        "projectId": "projectId",
        "cycleId": "cycleId",
        "delegateId": "delegateId",
    }
    for input_key, property_key in optional_fields.items():
        if (value := properties.get(property_key)) is not None and value != "":
            input_data[input_key] = value

    if (priority := properties.get("priority")) is not None and priority != "":
        input_data["priority"] = _parse_priority(priority)

    label_ids = properties.get("labelIds")
    if isinstance(label_ids, list):
        input_data["labelIds"] = label_ids

    return input_data


def require_property_from_dict(properties: dict[str, Any], name: str) -> Any:
    value = properties.get(name)
    if value is None or value == "":
        raise MissingExecutionPropertyError(f"{name} is required")
    return value


def _parse_priority(value: Any) -> int:
    try:
        priority = int(value)
    except (TypeError, ValueError) as error:
        raise MissingExecutionPropertyError(
            "priority must be an integer from 0 to 4"
        ) from error
    if priority not in range(5):
        raise MissingExecutionPropertyError("priority must be an integer from 0 to 4")
    return priority
