from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from linear.actions.abstract_linear_executor import AbstractLinearExecutor
from linear.actions.utils import optional_string, require_property
from linear.core.mutations import IssueMutations
from linear.helpers.exceptions import MissingExecutionPropertyError


class ChangeStatusExecutor(AbstractLinearExecutor):
    ACTION_NAME = "change_status"

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        issue_id = run.execution_properties.get("issueId")
        return str(issue_id) if issue_id else None

    async def execute(self, run: IntegrationRun) -> None:
        issue_id = require_property(run, "issueId")
        state_id = optional_string(run.execution_properties.get("stateId"))
        state_name = optional_string(run.execution_properties.get("stateName"))

        if not state_id and not state_name:
            raise MissingExecutionPropertyError("stateId or stateName is required")

        mutations = IssueMutations(self.client)
        if not state_id and state_name:
            state_id = await mutations.resolve_state_id(issue_id, state_name)

        await ocean.port_client.post_run_log(
            run,
            f"Changing status of issue {issue_id}",
            should_raise=False,
        )

        issue = await mutations.update_issue(issue_id, {"stateId": state_id})
        state = issue.get("state", {})
        state_label = state.get("name") if isinstance(state, dict) else state_id

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=f"Changed issue {issue['identifier']} status to {state_label}",
        )
        logger.info(
            "Changed Linear issue status",
            issue_id=issue["id"],
            state_id=state_id,
        )
