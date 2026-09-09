from typing import Any, Self

from pydantic import BaseModel, ConfigDict, ValidationError
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun

from linear.helpers.exceptions import MissingExecutionPropertyError


class LinearActionInput(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    @classmethod
    def from_execution_properties(cls, execution_properties: dict[str, Any]) -> Self:
        try:
            return cls.model_validate(execution_properties)
        except ValidationError as error:
            raise MissingExecutionPropertyError(str(error)) from error


def require_non_empty_str(value: Any) -> str:
    if value is None or (isinstance(value, str) and not str(value).strip()):
        raise ValueError("is required")
    return str(value)


def parse_priority(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        priority = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError("priority must be an integer from 0 to 4") from error
    if priority not in range(5):
        raise ValueError("priority must be an integer from 0 to 4")
    return priority


def optional_payload_fields(**fields: Any) -> dict[str, Any]:
    return {
        key: value
        for key, value in fields.items()
        if value is not None and value != ""
    }


def set_issue_run_output(run: IntegrationRun, issue: dict[str, Any]) -> None:
    if isinstance(run, WorkflowNodeRun):
        run.output = {
            "identifier": issue["identifier"],
            "issueId": str(issue["id"]),
            "issueUrl": issue.get("url") or "",
        }
