from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import WorkflowNodeRun
from port_ocean.exceptions.execution_manager import ActionExecutionError

from actions.abstract_executor import AbstractCursorExecutor
from actions.create_agent.context import CreateAgentContext
from actions.create_agent.handlers import CreateAgentHandler
from actions.request_bodies import parse_v1_create_body
from actions.utils import build_v1_create_body
from clients.endpoints import V1_AGENTS
from integration import ObjectKind


class CreateAgentV1Handler(CreateAgentHandler):
    async def execute(
        self, executor: AbstractCursorExecutor, ctx: CreateAgentContext
    ) -> None:
        run = ctx.run
        body = build_v1_create_body(
            prompt=ctx.prompt,
            repository=ctx.repository,
            ref=ctx.ref,
            pr_url=ctx.pr_url,
            model=ctx.model,
            auto_create_pr=ctx.auto_create_pr,
            config=ctx.config,
        )
        parse_v1_create_body(body)
        try:
            response = await executor.client.send_api_request(
                "POST", V1_AGENTS, json_body=body
            )
        except Exception as error:
            raise ActionExecutionError(
                f"Failed to create Cursor agent: {error}"
            ) from error

        agent = response.get("agent") or {}
        run_obj = response.get("run") or {}
        agent_id = agent.get("id")
        run_id = run_obj.get("id")
        if not agent_id:
            raise ActionExecutionError(
                "Cursor agent was created but no id was returned"
            )

        logger.info(f"Created Cursor agent {agent_id} (v1) for run {run.id}")

        await executor.register_entity(ObjectKind.AGENT, agent, run)
        if run_id:
            run_raw = dict(run_obj)
            run_raw.setdefault("agentId", agent_id)
            await executor.register_entity(ObjectKind.RUN, run_raw, run)

        if isinstance(run, WorkflowNodeRun):
            run.output["agentId"] = agent_id
            run.output["runId"] = run_id
            run.output["url"] = agent.get("url")

        await ocean.port_client.report_run_completed(
            run, True, f"Created agent {agent_id}"
        )
