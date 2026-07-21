from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun
from port_ocean.exceptions.execution_manager import ActionExecutionError

from actions.abstract_executor import AbstractCursorExecutor
from actions.request_bodies import parse_v1_run_body
from actions.exceptions import InvalidActionParametersException
from actions.utils import (
    WEBHOOK_PATH,
    build_agent_link,
    build_v1_run_body,
)
from clients.endpoints import v1_agent_runs
from integration import ObjectKind
from webhook_processors.cursor_agent_webhook_processor import (
    CursorAgentWebhookProcessor,
)


class TriggerAgentExecutor(AbstractCursorExecutor):
    """Executor for the `trigger_agent` action.

    Sends a follow-up prompt to an existing Cursor cloud agent via the v1
    Create Run API so `config` (`mcpServers`, `mode`, `prompt.images`) always
    applies,
    even when the agent was originally created via v0. Cursor only allows one
    active run per agent at a time, so runs targeting the same agent are
    serialized via `PARTITION_KEY`.

    When `reportCompletion` is set and the agent already has a webhook
    registered (only possible when originally created via v0 create with
    `reportCompletion` and a reachable public URL), leaves the Port run
    `IN_PROGRESS` and waits for `CursorAgentWebhookProcessor`. Otherwise
    completes the Port run immediately after the follow-up HTTP call succeeds.
    """

    ACTION_NAME = "trigger_agent"
    WEBHOOK_PROCESSOR_CLASS = CursorAgentWebhookProcessor
    WEBHOOK_PATH = WEBHOOK_PATH

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        agent_id = run.execution_properties.get("agentId")
        return agent_id if isinstance(agent_id, str) else None

    async def execute(self, run: IntegrationRun) -> None:
        props = run.execution_properties
        agent_id = props.get("agentId")

        report_completion = bool(props.get("reportCompletion", False))
        config = props.get("config")
        if config is None:
            config = {}
        elif not isinstance(config, dict):
            raise InvalidActionParametersException("config must be an object")

        body = build_v1_run_body(prompt=props.get("prompt"), config=config)
        parse_v1_run_body(body)
        try:
            response = await self.client.send_api_request(
                "POST", v1_agent_runs(agent_id), json_body=body
            )
        except Exception as error:
            raise ActionExecutionError(
                f"Failed to trigger Cursor agent {agent_id}: {error}"
            ) from error

        run_obj = response.get("run") or {}
        run_id = run_obj.get("id")

        logger.info(
            f"Triggered Cursor agent {agent_id} via run {run_id} (v1 follow-up) "
            f"for Port run {run.id}"
        )

        if run_id:
            run_raw = dict(run_obj)
            run_raw.setdefault("agentId", agent_id)
            await self.register_entity(ObjectKind.RUN, run_raw, run)

        if isinstance(run, WorkflowNodeRun):
            run.output["agentId"] = agent_id
            run.output["runId"] = run_id

        if report_completion and await self._agent_has_registered_webhook(agent_id):
            if not run_id:
                raise ActionExecutionError(
                    f"Cursor agent {agent_id} returned no run id for follow-up"
                )
            await ocean.port_client.update_run_started(
                run,
                build_agent_link(self.client.get_console_host(), agent_id),
                run_id,
                extra_output={"agentId": agent_id, "runId": run_id},
            )
        else:
            await ocean.port_client.report_run_completed(
                run, True, f"Follow-up sent to agent {agent_id}"
            )

    async def _agent_has_registered_webhook(self, agent_id: str) -> bool:
        """Whether this agent was ever tracked via v0 create with a webhook.

        Cursor only registers a webhook at v0 agent launch time. The integration
        records that on the initial ``create_agent`` run by setting the Cursor
        agent id as ``externalRunId``. Best-effort: treated as untracked if the
        lookup fails.
        """
        try:
            prior_run = await ocean.port_client.find_run_by_external_id(agent_id)
        except Exception as error:
            logger.warning(
                f"Failed to look up webhook-tracked runs for Cursor agent {agent_id} "
                f"(treating as untracked): {error}"
            )
            return False
        return prior_run is not None
