from typing import Any

from anthropic.types.beta.sessions.beta_managed_agents_session_requires_action import (
    BetaManagedAgentsSessionRequiresAction,
)
from anthropic.types.beta.sessions.beta_managed_agents_session_status_idle_event import (
    BetaManagedAgentsSessionStatusIdleEvent,
)
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import ActionRun, WorkflowNodeRun
from port_ocean.exceptions.execution_manager import ActionExecutionError

from actions.abstract_executor import AbstractAnthropicExecutor
from actions.exceptions import InvalidActionParametersException
from actions.utils import (
    build_external_id,
    build_session_link,
    normalize_session_config,
)
from integration import ObjectKind
from webhook_processors.registry import WEBHOOK_PATH
from webhook_processors.trigger_agent_webhook_processor import (
    TriggerAgentWebhookProcessor,
)


class TriggerAgentExecutor(AbstractAnthropicExecutor):
    """Executor for the `trigger_agent` action.

    Starts a new session or continues an idle session, sends a user message, and
    marks the run as started with an external ID derived from the session and the
    sent message event. Completion is reported asynchronously by
    `TriggerAgentWebhookProcessor` when the session reaches a terminal state.

    New sessions have no partition key and may execute in parallel, since each
    creates an independent session; continuations are serialized per session id
    to avoid two runs racing on the same session.
    """

    ACTION_NAME = "trigger_agent"
    WEBHOOK_PROCESSOR_CLASS = TriggerAgentWebhookProcessor
    WEBHOOK_PATH = WEBHOOK_PATH

    async def _get_partition_key(self, run: ActionRun | WorkflowNodeRun) -> str | None:
        session_id = run.execution_properties.get("sessionId")
        if session_id:
            return session_id
        return None

    async def _ensure_session_continuable(self, session_id: str) -> dict[str, Any]:
        session = await self.client.get_session(session_id)
        status = session.get("status")
        if status != "idle":
            raise ActionExecutionError(
                f"Session {session_id} cannot be continued (status={status!r}); "
                "only idle sessions accept a new prompt"
            )

        async for batch in self.client.get_session_events(
            session_id,
            types=["session.status_idle"],
            order="desc",
            limit=1,
        ):
            idle_event = batch[0]
            if isinstance(idle_event, BetaManagedAgentsSessionStatusIdleEvent):
                stop_reason = idle_event.stop_reason
                if isinstance(stop_reason, BetaManagedAgentsSessionRequiresAction):
                    raise ActionExecutionError(
                        f"Session {session_id} is waiting for user action "
                        "(tool confirmation or similar) and cannot accept a plain prompt"
                    )
            break

        return session

    async def execute(self, run: ActionRun | WorkflowNodeRun) -> None:
        props = run.execution_properties
        agent_id = props.get("agentId")
        environment_id = props.get("environmentId")
        prompt = props.get("prompt")
        session_id = props.get("sessionId")
        config = props.get("config")
        if config is None:
            config = {}
        elif not isinstance(config, dict):
            raise InvalidActionParametersException("config must be an object")

        if not (agent_id and prompt):
            raise InvalidActionParametersException("agentId and prompt are required")

        if session_id:
            session = await self._ensure_session_continuable(session_id)
            resolved_session_id = session_id
        else:
            if not environment_id:
                raise InvalidActionParametersException(
                    "environmentId is required when starting a new session"
                )
            api_config = await normalize_session_config(config)
            session = await self.client.create_session(
                agent_id,
                environment_id,
                extra=api_config or None,
            )
            resolved_session_id = session.get("id")
            if not resolved_session_id or not isinstance(resolved_session_id, str):
                raise ActionExecutionError(
                    "Session was created but no session id was returned"
                )

        user_message = await self.client.send_user_message(resolved_session_id, prompt)
        logger.info(
            f"Triggered Claude agent {agent_id} via session {resolved_session_id} "
            f"(message {user_message.id}) for run {run.id}"
        )

        # Reflect the session in the catalog (no-op if the `session` kind is
        # not mapped). Status updates arrive later via webhooks. Best-effort:
        # never fails the run.
        await self.register_entity(ObjectKind.SESSION, session, run)

        external_id = build_external_id(resolved_session_id, user_message.id)
        await ocean.port_client.update_run_started(
            run,
            build_session_link(
                self.client.get_console_host(),
                self.client.get_workspace_id(),
                resolved_session_id,
            ),
            external_id,
            extra_output={
                "sessionId": resolved_session_id,
                "userMessageEventId": user_message.id,
            },
        )

        if not props.get("reportSessionStatus", False):
            await ocean.port_client.report_run_completed(
                run, True, f"Prompt sent to session {resolved_session_id}"
            )
