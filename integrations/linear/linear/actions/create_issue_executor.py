from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from linear.actions.abstract_linear_executor import AbstractLinearExecutor
from linear.actions.types import CreateIssuePayload
from linear.actions.utils import set_issue_run_output
from linear.core.mutations import IssueMutations
from linear.actions.exceptions import LinearActionError


class CreateIssueExecutor(AbstractLinearExecutor):
    ACTION_NAME = "create_issue"

    async def execute(self, run: IntegrationRun) -> None:
        payload = CreateIssuePayload.from_execution_properties(run.execution_properties)

        await ocean.port_client.post_run_log(
            run,
            f"Creating issue '{payload.title}' in team {payload.teamId}",
            should_raise=False,
        )

        mutations = IssueMutations(self.client)
        try:
            issue = await mutations.create_issue(payload.to_mutation())
        except Exception as error:
            raise LinearActionError(str(error), status_label="Create failed") from error
        message = f"Created issue {issue.identifier}: {issue.url}"
        set_issue_run_output(run, issue)

        logger.info(
            "Created Linear issue",
            issue_id=issue.id,
            identifier=issue.identifier,
        )
        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=message,
            status_label="Issue created",
        )
