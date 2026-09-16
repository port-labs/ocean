from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from linear.actions.abstract_linear_executor import AbstractLinearExecutor
from linear.actions.types import ChangeIssueStatusPayload
from linear.actions.utils import set_issue_run_output
from linear.core.mutations import IssueMutations


class ChangeIssueStatusExecutor(AbstractLinearExecutor):
    ACTION_NAME = "change_issue_status"

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        issue_id = run.execution_properties.get("issueId")
        return str(issue_id) if issue_id else None

    async def execute(self, run: IntegrationRun) -> None:
        payload = ChangeIssueStatusPayload.from_execution_properties(
            run.execution_properties
        )

        mutations = IssueMutations(self.client)
        state_id = await mutations.resolve_state_id(payload.issueId, payload.stateName)

        await ocean.port_client.post_run_log(
            run,
            f"Changing status of issue {payload.issueId} to {payload.stateName}",
            status_label="Changing status",
            should_raise=False,
        )

        issue = await mutations.update_issue(
            payload.issueId, payload.build_mutation(state_id)
        )
        state_label = issue.state.name if issue.state else payload.stateName
        message = f"Changed issue {issue.identifier} status to {state_label}"
        set_issue_run_output(run, issue)

        logger.info(
            "Changed Linear issue status",
            issue_id=issue.id,
            state_id=state_id,
        )
        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=message,
            status_label="Status changed",
        )
