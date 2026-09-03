from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import WorkflowNodeRun
from port_ocean.exceptions.execution_manager import ActionExecutionError

from actions.abstract_executor import AbstractCursorExecutor
from actions.create_agent.context import CreateAgentContext
from actions.create_agent.handlers import CreateAgentHandler
from actions.exceptions import InvalidActionParametersException
from actions.request_bodies import parse_v0_create_body
from actions.utils import (
    build_agent_link,
    build_v0_launch_body,
    build_webhook_config,
    build_webhook_url,
)
from clients.endpoints import V0_AGENTS
from core.webhook_signing import get_webhook_signing_secret
from exporter_factory import create_runs_exporter
from integration import ObjectKind

LAUNCHING_STATUS_LABEL = "Launching agent"
LAUNCH_FAILED_STATUS_LABEL = "Launch failed"
AGENT_RUNNING_STATUS_LABEL = "Agent running"
AGENT_LAUNCHED_STATUS_LABEL = "Agent launched"


class CreateAgentV0Handler(CreateAgentHandler):
    async def execute(
        self, executor: AbstractCursorExecutor, ctx: CreateAgentContext
    ) -> None:
        run = ctx.run
        body = build_v0_launch_body(
            prompt=ctx.prompt,
            repository=ctx.repository,
            ref=ctx.ref,
            pr_url=ctx.pr_url,
            model=ctx.model,
            auto_create_pr=ctx.auto_create_pr,
            webhook=None,
            config=ctx.config,
        )
        parse_v0_create_body(body, report_completion=ctx.report_completion)

        if ctx.report_completion:
            webhook_url = build_webhook_url()
            if webhook_url is None:
                raise InvalidActionParametersException(
                    "reportCompletion requires a reachable public URL (OCEAN__BASE_URL)"
                )
            body["webhook"] = build_webhook_config(
                webhook_url, get_webhook_signing_secret()
            )

        await ocean.port_client.post_run_log(
            run,
            "Launching Cursor agent",
            status_label=LAUNCHING_STATUS_LABEL,
            should_raise=False,
        )

        try:
            agent = await executor.client.send_api_request(
                "POST", V0_AGENTS, json_body=body
            )
        except Exception as error:
            raise ActionExecutionError(
                f"Failed to launch Cursor agent: {error}",
                status_label=LAUNCH_FAILED_STATUS_LABEL,
            ) from error

        agent_id = agent.get("id")
        if not agent_id:
            raise ActionExecutionError(
                "Cursor agent was launched but no id was returned",
                status_label=LAUNCH_FAILED_STATUS_LABEL,
            )

        logger.info(
            f"Launched Cursor agent {agent_id} (v0, "
            f"{'tracked' if ctx.report_completion else 'fire-and-forget'}) "
            f"for run {run.id}"
        )

        await executor.register_entity(ObjectKind.AGENT, agent, run)
        try:
            runs = await create_runs_exporter().list_first_page(agent_id)
        except Exception as error:
            logger.warning(
                f"Failed to list runs for Cursor agent {agent_id} after v0 launch "
                f"(catalog run upsert skipped): {error}"
            )
            runs = []
        if runs:
            run_raw = dict(runs[0])
            run_raw.setdefault("agentId", agent_id)
            await executor.register_entity(ObjectKind.RUN, run_raw, run)

        if isinstance(run, WorkflowNodeRun):
            run.output["agentId"] = agent_id
            run.output["status"] = agent.get("status")

        if ctx.report_completion:
            await ocean.port_client.update_run_started(
                run,
                build_agent_link(executor.client.get_console_host(), agent_id),
                agent_id,
                extra_output={"agentId": agent_id},
                status_label=AGENT_RUNNING_STATUS_LABEL,
            )
        else:
            await ocean.port_client.report_run_completed(
                run,
                True,
                f"Launched agent {agent_id}",
                status_label=AGENT_LAUNCHED_STATUS_LABEL,
            )
