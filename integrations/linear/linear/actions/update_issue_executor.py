from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun
from pydantic.v1 import validator

from linear.actions.abstract_linear_executor import AbstractLinearExecutor
from linear.actions.utils import LinearActionInput, build_issue_update_input, require_non_empty_str
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
    priority: Any = None
    delegateId: str | None = None
    labelIds: list[str] | None = None

    @validator("issueId", pre=True, always=True)
    def require_issue_id(cls, value: Any, field: Any) -> str:
        return require_non_empty_str(value, field)


class UpdateIssueExecutor(AbstractLinearExecutor):
    ACTION_NAME = "update_issue"

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        issue_id = run.execution_properties.get("issueId")
        return str(issue_id) if issue_id else None

    async def execute(self, run: IntegrationRun) -> None:
        inputs = UpdateIssueInput.from_execution_properties(run.execution_properties)
        issue_input = build_issue_update_input(inputs.dict(exclude_none=True))
        if not issue_input:
            raise MissingExecutionPropertyError(
                "At least one update field is required (title, description, assigneeId, stateId, projectId, cycleId, priority, delegateId, or labelIds)"
            )

        await ocean.port_client.post_run_log(
            run,
            f"Updating issue {inputs.issueId}",
            should_raise=False,
        )

        mutations = IssueMutations(self.client)
        issue = await mutations.update_issue(inputs.issueId, issue_input)

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=f"Updated issue {issue['identifier']}: {issue['url']}",
        )
        logger.info("Updated Linear issue", issue_id=issue["id"])
