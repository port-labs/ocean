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
from linear.core.exporters import IssueExporter
from linear.core.exporters.issue_exporter import GetIssueOptions
from linear.core.mutations import IssueMutations
from linear.helpers.exceptions import MissingExecutionPropertyError


class CreateSubIssueInput(LinearActionPayload):
    parentId: NonEmptyStr
    title: NonEmptyStr
    teamId: OptionalStr = None
    description: OptionalStr = None
    assigneeId: OptionalStr = None
    stateId: OptionalStr = None
    priority: OptionalPriority = None


class CreateSubIssueExecutor(AbstractLinearExecutor):
    ACTION_NAME = "create_sub_issue"

    async def execute(self, run: IntegrationRun) -> None:
        inputs = CreateSubIssueInput.from_execution_properties(run.execution_properties)
        if not inputs.teamId:
            exporter = IssueExporter(self.client)
            parent_issue = await exporter.get_resource(
                GetIssueOptions(resource_id=str(inputs.parentId))
            )
            team = parent_issue.get("team")
            if not isinstance(team, dict) or not team.get("id"):
                raise MissingExecutionPropertyError(
                    "teamId is required when the parent issue team cannot be resolved"
                )
            inputs.teamId = str(team["id"])

        payload = inputs.to_api_payload()

        await ocean.port_client.post_run_log(
            run,
            f"Creating sub-issue '{payload['title']}' under {inputs.parentId}",
            status_label="Creating issue",
            should_raise=False,
        )

        mutations = IssueMutations(self.client)
        issue = await mutations.create_issue(payload)
        message = f"Created sub-issue {issue['identifier']}: {issue['url']}"
        set_issue_run_output(run, issue)

        logger.info(
            "Created Linear sub-issue",
            issue_id=issue["id"],
            parent_id=inputs.parentId,
        )
        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=message,
            status_label="Issue created",
        )
