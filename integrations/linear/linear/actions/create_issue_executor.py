from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun
from pydantic import field_validator

from linear.actions.abstract_linear_executor import AbstractLinearExecutor
from linear.actions.utils import (
    LinearActionInput,
    optional_payload_fields,
    parse_priority,
    require_non_empty_str,
    set_issue_run_output,
)
from linear.core.mutations import IssueMutations


class CreateIssueInput(LinearActionInput):
    teamId: str
    title: str
    description: str | None = None
    assigneeId: str | None = None
    stateId: str | None = None
    projectId: str | None = None
    cycleId: str | None = None
    priority: int | None = None
    labelIds: list[str] | None = None

    @field_validator("teamId", "title", mode="before")
    @classmethod
    def require_required_fields(cls, value: Any) -> str:
        return require_non_empty_str(value)

    @field_validator("priority", mode="before")
    @classmethod
    def validate_priority(cls, value: Any) -> int | None:
        return parse_priority(value)

    def to_api_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"teamId": self.teamId, "title": self.title}
        payload.update(
            optional_payload_fields(
                description=self.description,
                assigneeId=self.assigneeId,
                stateId=self.stateId,
                projectId=self.projectId,
                cycleId=self.cycleId,
            )
        )
        if self.priority is not None:
            payload["priority"] = self.priority
        if self.labelIds:
            payload["labelIds"] = self.labelIds
        return payload


class CreateIssueExecutor(AbstractLinearExecutor):
    ACTION_NAME = "create_issue"

    async def execute(self, run: IntegrationRun) -> None:
        inputs = CreateIssueInput.from_execution_properties(run.execution_properties)
        issue_input = inputs.to_api_payload()

        await ocean.port_client.post_run_log(
            run,
            f"Creating issue '{issue_input['title']}' in team {issue_input['teamId']}",
            status_label="Creating issue",
            should_raise=False,
        )

        mutations = IssueMutations(self.client)
        issue = await mutations.create_issue(issue_input)
        message = f"Created issue {issue['identifier']}: {issue['url']}"
        set_issue_run_output(run, issue)

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=message,
            status_label="Issue created",
        )
        logger.info(
            "Created Linear issue",
            issue_id=issue["id"],
            identifier=issue.get("identifier"),
        )
