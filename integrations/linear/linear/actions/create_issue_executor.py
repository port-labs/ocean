from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from linear.actions.abstract_linear_executor import AbstractLinearExecutor
from linear.actions.utils import (
    LinearActionPayload,
    NonEmptyStr,
    OptionalPriority,
    OptionalStr,
    set_issue_run_output,
)
from linear.core.mutations import IssueMutations


class CreateIssueInput(LinearActionPayload):
    teamId: NonEmptyStr
    title: NonEmptyStr
    description: OptionalStr = None
    assigneeId: OptionalStr = None
    stateId: OptionalStr = None
    projectId: OptionalStr = None
    cycleId: OptionalStr = None
    priority: OptionalPriority = None
    labelIds: list[str] | None = None


class CreateIssueExecutor(AbstractLinearExecutor):
    ACTION_NAME = "create_issue"

    async def execute(self, run: IntegrationRun) -> None:
        inputs = CreateIssueInput.from_execution_properties(run.execution_properties)
        payload = inputs.to_api_payload()

        await ocean.port_client.post_run_log(
            run,
            f"Creating issue '{payload['title']}' in team {payload['teamId']}",
            status_label="Creating issue",
            should_raise=False,
        )

        mutations = IssueMutations(self.client)
        issue = await mutations.create_issue(payload)
        message = f"Created issue {issue['identifier']}: {issue['url']}"
        set_issue_run_output(run, issue)

        logger.info(
            "Created Linear issue",
            issue_id=issue["id"],
            identifier=issue.get("identifier"),
        )
        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=message,
            status_label="Issue created",
        )
