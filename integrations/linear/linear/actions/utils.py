from typing import Any

from port_ocean.core.models import IntegrationRun

from linear.helpers.exceptions import MissingExecutionPropertyError


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
        "parentId": "parentId",
        "priority": "priority",
        "estimate": "estimate",
        "dueDate": "dueDate",
    }
    for input_key, property_key in optional_fields.items():
        if (value := properties.get(property_key)) is not None and value != "":
            input_data[input_key] = value

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
        "priority": "priority",
        "estimate": "estimate",
        "dueDate": "dueDate",
        "delegateId": "delegateId",
    }
    for input_key, property_key in optional_fields.items():
        if (value := properties.get(property_key)) is not None and value != "":
            input_data[input_key] = value

    label_ids = properties.get("labelIds")
    if isinstance(label_ids, list) and label_ids:
        input_data["labelIds"] = label_ids

    return input_data


def require_property_from_dict(properties: dict[str, Any], name: str) -> Any:
    value = properties.get(name)
    if value is None or value == "":
        raise MissingExecutionPropertyError(f"{name} is required")
    return value
