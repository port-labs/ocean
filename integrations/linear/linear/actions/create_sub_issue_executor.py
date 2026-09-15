from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from linear.actions.abstract_linear_executor import AbstractLinearExecutor
from linear.actions.types import CreateSubIssuePayload
from linear.actions.utils import set_issue_run_output
from linear.core.exporters import IssueExporter
from linear.core.exporters.issue_exporter import GetIssueOptions
from linear.core.mutations import IssueMutations
from linear.helpers.exceptions import MissingExecutionPropertyError


class CreateSubIssueExecutor(AbstractLinearExecutor):
    ACTION_NAME = "create_sub_issue"

    async def _resolve_team_id(self, payload: CreateSubIssuePayload) -> None:
        if payload.teamId:
            return

        exporter = IssueExporter(self.client)
        parent_issue = await exporter.get_resource(
            GetIssueOptions(resource_id=str(payload.parentId))
        )
        team = parent_issue.get("team")
        if not isinstance(team, dict) or not team.get("id"):
            raise MissingExecutionPropertyError(
                "teamId is required when the parent issue team cannot be resolved"
            )
        payload.teamId = str(team["id"])

    async def execute(self, run: IntegrationRun) -> None:
        payload = CreateSubIssuePayload.from_execution_properties(
            run.execution_properties
        )
        await self._resolve_team_id(payload)

        await ocean.port_client.post_run_log(
            run,
            f"Creating sub-issue '{payload.title}' under {payload.parentId}",
            status_label="Creating issue",
            should_raise=False,
        )

        mutations = IssueMutations(self.client)
        issue = await mutations.create_issue(payload.to_mutation())
        message = f"Created sub-issue {issue.identifier}: {issue.url}"
        set_issue_run_output(run, issue)

        logger.info(
            "Created Linear sub-issue",
            issue_id=issue.id,
            parent_id=payload.parentId,
        )
        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=message,
            status_label="Issue created",
        )
