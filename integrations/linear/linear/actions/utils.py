from typing import Annotated, Any, ClassVar, Self

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, ValidationError
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun

from linear.helpers.exceptions import MissingExecutionPropertyError


def _empty_to_none(value: Any) -> Any:
    if value == "":
        return None
    return value


NonEmptyStr = Annotated[str, Field(min_length=1)]
OptionalStr = Annotated[str | None, BeforeValidator(_empty_to_none)]
Priority = Annotated[int, Field(ge=0, le=4)]
OptionalPriority = Annotated[Priority | None, BeforeValidator(_empty_to_none)]


class LinearActionPayload(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    api_payload_exclude: ClassVar[frozenset[str]] = frozenset()

    def to_api_payload(self) -> dict[str, Any]:
        return self.model_dump(
            exclude=self.api_payload_exclude,
            exclude_none=True,
        )

    @classmethod
    def from_execution_properties(cls, execution_properties: dict[str, Any]) -> Self:
        try:
            return cls.model_validate(execution_properties)
        except ValidationError as error:
            raise MissingExecutionPropertyError(str(error)) from error


def set_issue_run_output(run: IntegrationRun, issue: dict[str, Any]) -> None:
    if isinstance(run, WorkflowNodeRun):
        run.output = {
            "identifier": issue["identifier"],
            "issueId": str(issue["id"]),
            "issueUrl": issue.get("url") or "",
        }
