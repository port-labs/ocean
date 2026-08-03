from port_ocean.core.models import IntegrationRun

from actions.abstract_executor import AbstractCursorExecutor
from actions.create_agent.context import CreateAgentContext
from actions.create_agent.handlers import get_handler


class CreateAgentExecutor(AbstractCursorExecutor):
    """Executor for the `create_agent` action.

    Launches a new Cursor cloud agent with its initial prompt. Cursor's create
    endpoints always start a run and billable work immediately - there is no
    config-only create. v1 create requires `repository`, `config.repos`, or
    `config.env` in the merged request body (Port policy). v0 source requirements
    are enforced by Cursor.

    `apiVersion` selects the Cursor create endpoint (`v0` or `v1`). On v0,
    `reportCompletion` optionally attaches a webhook and leaves the Port run
    `IN_PROGRESS` until `CursorAgentWebhookProcessor` concludes it. On v1,
    the Port run always completes immediately after launch (`reportCompletion`
    is rejected - v1 has no webhooks).
    """

    ACTION_NAME = "create_agent"

    async def execute(self, run: IntegrationRun) -> None:
        ctx = CreateAgentContext.from_run(run)
        await get_handler(ctx.api_version).execute(self, ctx)
