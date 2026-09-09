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
from linear.helpers.exceptions import MissingExecutionPropertyError


class UpdateIssueInput(LinearActionInput):
    issueId: str
    title: str | None = None
    description: str | None = None
    assigneeId: str | None = None
    stateId: str | None = None
    projectId: str | None = None
    cycleId: str | None = None
    priority: int | None = None
    delegateId: str | None = None
    labelIds: list[str] | None = None

    @field_validator("issueId", mode="before")
    @classmethod
    def require_issue_id(cls, value: Any) -> str:
        return require_non_empty_str(value)

    @field_validator("priority", mode="before")
    @classmethod
    def validate_priority(cls, value: Any) -> int | None:
        return parse_priority(value)

    def to_api_payload(self) -> dict[str, Any]:
        payload = optional_payload_fields(
            title=self.title,
            description=self.description,
            assigneeId=self.assigneeId,
            stateId=self.stateId,
            projectId=self.projectId,
            cycleId=self.cycleId,
            delegateId=self.delegateId,
        )
        if self.priority is not None:
            payload["priority"] = self.priority
        if self.labelIds is not None:
            payload["labelIds"] = self.labelIds
        return payload


class UpdateIssueExecutor(AbstractLinearExecutor):
    ACTION_NAME = "update_issue"

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        issue_id = run.execution_properties.get("issueId")
        return str(issue_id) if issue_id else None

    async def execute(self, run: IntegrationRun) -> None:
        inputs = UpdateIssueInput.from_execution_properties(run.execution_properties)
        issue_input = inputs.to_api_payload()
        if not issue_input:
            raise MissingExecutionPropertyError(
                "At least one update field is required (title, description, assigneeId, stateId, projectId, cycleId, priority, delegateId, or labelIds)"
            )

        await ocean.port_client.post_run_log(
            run,
            f"Updating issue {inputs.issueId}",
            status_label="Updating issue",
            should_raise=False,
        )

        mutations = IssueMutations(self.client)
        issue = await mutations.update_issue(inputs.issueId, issue_input)
        message = f"Updated issue {issue['identifier']}: {issue['url']}"
        set_issue_run_output(run, issue)

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=message,
            status_label="Issue updated",
        )
        logger.info("Updated Linear issue", issue_id=issue["id"])
