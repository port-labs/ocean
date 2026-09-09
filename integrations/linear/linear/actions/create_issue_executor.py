from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from linear.actions.abstract_linear_executor import AbstractLinearExecutor
from linear.actions.utils import build_issue_create_input, require_property
from linear.core.mutations import IssueMutations


class CreateIssueExecutor(AbstractLinearExecutor):
    ACTION_NAME = "create_issue"

    async def execute(self, run: IntegrationRun) -> None:
        properties = run.execution_properties
        require_property(run, "teamId")
        require_property(run, "title")
        issue_input = build_issue_create_input(properties)

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
