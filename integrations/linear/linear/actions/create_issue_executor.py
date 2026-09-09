from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun
from pydantic.v1 import validator

from linear.actions.abstract_linear_executor import AbstractLinearExecutor
from linear.actions.utils import LinearActionInput, build_issue_create_input, require_non_empty_str
from linear.core.mutations import IssueMutations


class CreateIssueInput(LinearActionInput):
    teamId: str
    title: str
    description: str | None = None
    assigneeId: str | None = None
    stateId: str | None = None
    projectId: str | None = None
    cycleId: str | None = None
    priority: Any = None
    labelIds: list[str] | None = None

    @validator("teamId", "title", pre=True, always=True)
    def require_required_fields(cls, value: Any, field: Any) -> str:
        return require_non_empty_str(value, field)


class CreateIssueExecutor(AbstractLinearExecutor):
    ACTION_NAME = "create_issue"

    async def execute(self, run: IntegrationRun) -> None:
        inputs = CreateIssueInput.from_execution_properties(run.execution_properties)
        issue_input = build_issue_create_input(inputs.dict(exclude_none=True))

        await ocean.port_client.post_run_log(
            run,
            f"Creating issue '{issue_input['title']}' in team {issue_input['teamId']}",
            should_raise=False,
        )

        mutations = IssueMutations(self.client)
        issue = await mutations.create_issue(issue_input)

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=f"Created issue {issue['identifier']}: {issue['url']}",
        )
        logger.info(
            "Created Linear issue",
            issue_id=issue["id"],
            identifier=issue.get("identifier"),
        )
