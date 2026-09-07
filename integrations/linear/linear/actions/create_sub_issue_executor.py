from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from linear.actions.abstract_linear_executor import AbstractLinearExecutor
from linear.actions.utils import build_issue_create_input, require_property
from linear.helpers.exceptions import MissingExecutionPropertyError


class CreateSubIssueExecutor(AbstractLinearExecutor):
    ACTION_NAME = "create_sub_issue"

    async def execute(self, run: IntegrationRun) -> None:
        properties = run.execution_properties
        parent_id = require_property(run, "parentId")
        require_property(run, "title")
        issue_input = build_issue_create_input(properties)
        issue_input["parentId"] = parent_id

        if not issue_input.get("teamId"):
            parent_issue = await self.client.get_single_issue(str(parent_id))
            team = parent_issue.get("team")
            if not isinstance(team, dict) or not team.get("id"):
                raise MissingExecutionPropertyError(
                    "teamId is required when the parent issue team cannot be resolved"
                )
            issue_input["teamId"] = team["id"]

        await ocean.port_client.post_run_log(
            run,
            f"Creating sub-issue '{issue_input['title']}' under {parent_id}",
            should_raise=False,
        )

        issue = await self.client.create_issue(issue_input)

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=f"Created sub-issue {issue['identifier']}: {issue['url']}",
        )
        logger.info(
            "Created Linear sub-issue",
            issue_id=issue["id"],
            parent_id=parent_id,
        )
