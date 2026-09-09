from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun
from pydantic.v1 import validator

from linear.actions.abstract_linear_executor import AbstractLinearExecutor
from linear.actions.utils import LinearActionInput, build_issue_create_input, require_non_empty_str
from linear.core.exporters import IssueExporter
from linear.core.exporters.issue_exporter import GetIssueOptions
from linear.core.mutations import IssueMutations
from linear.helpers.exceptions import MissingExecutionPropertyError


class CreateSubIssueInput(LinearActionInput):
    parentId: str
    title: str
    teamId: str | None = None
    description: str | None = None
    assigneeId: str | None = None
    stateId: str | None = None
    priority: Any = None

    @validator("parentId", "title", pre=True, always=True)
    def require_required_fields(cls, value: Any, field: Any) -> str:
        return require_non_empty_str(value, field)


class CreateSubIssueExecutor(AbstractLinearExecutor):
    ACTION_NAME = "create_sub_issue"

    async def execute(self, run: IntegrationRun) -> None:
        inputs = CreateSubIssueInput.from_execution_properties(run.execution_properties)
        issue_input = build_issue_create_input(inputs.dict(exclude_none=True))
        issue_input["parentId"] = inputs.parentId

        if not issue_input.get("teamId"):
            exporter = IssueExporter(self.client)
            parent_issue = await exporter.get_resource(
                GetIssueOptions(resource_id=str(inputs.parentId))
            )
            team = parent_issue.get("team")
            if not isinstance(team, dict) or not team.get("id"):
                raise MissingExecutionPropertyError(
                    "teamId is required when the parent issue team cannot be resolved"
                )
            issue_input["teamId"] = team["id"]

        await ocean.port_client.post_run_log(
            run,
            f"Creating sub-issue '{issue_input['title']}' under {inputs.parentId}",
            should_raise=False,
        )

        mutations = IssueMutations(self.client)
        issue = await mutations.create_issue(issue_input)

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=f"Created sub-issue {issue['identifier']}: {issue['url']}",
        )
        logger.info(
            "Created Linear sub-issue",
            issue_id=issue["id"],
            parent_id=inputs.parentId,
        )
