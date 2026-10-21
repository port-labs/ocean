from anthropic.types.beta.beta_managed_agents_session import BetaManagedAgentsSession
from anthropic.types.beta.sessions.beta_managed_agents_session_requires_action import (
    BetaManagedAgentsSessionRequiresAction,
)
from anthropic.types.beta.sessions.beta_managed_agents_session_status_idle_event import (
    BetaManagedAgentsSessionStatusIdleEvent,
)
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun
from port_ocean.exceptions.execution_manager import ActionExecutionError

from actions.abstract_executor import AbstractAnthropicExecutor
from actions.exceptions import InvalidActionParametersException
from actions.port_mcp import (
    agent_uses_port_mcp,
    prepare_port_mcp_session_config,
    refresh_port_mcp_session,
)
from actions.types import TriggerAgentSessionOutput
from actions.utils import (
    build_external_id,
    build_session_link,
    normalize_session_config,
)
from integration import ObjectKind
from stream_manager import get_stream_manager
from webhook_processors.registry import WEBHOOK_PATH
from webhook_processors.trigger_agent_webhook_processor import (
    TriggerAgentWebhookProcessor,
)

STARTING_STATUS_LABEL = "Sending prompt"
SESSION_RUNNING_STATUS_LABEL = "Session running"
PROMPT_SENT_STATUS_LABEL = "Prompt sent"
SESSION_NOT_CONTINUABLE_STATUS_LABEL = "Cannot continue"
SESSION_START_FAILED_STATUS_LABEL = "Start failed"


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

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        session_id = run.execution_properties.get("sessionId")
        if session_id:
            return session_id
        return None

    async def _ensure_session_continuable(
        self, session_id: str
    ) -> BetaManagedAgentsSession:
        session = await self.client.get_session(session_id)
        if session.status != "idle":
            raise ActionExecutionError(
                f"Session {session_id} cannot be continued "
                f"(status={session.status!r}); "
                "only idle sessions accept a new prompt",
                status_label=SESSION_NOT_CONTINUABLE_STATUS_LABEL,
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
                        "(tool confirmation or similar) and cannot accept a plain prompt",
                        status_label=SESSION_NOT_CONTINUABLE_STATUS_LABEL,
                    )
            break

        return session

    async def execute(self, run: IntegrationRun) -> None:
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
        new_environment_id = environment_id if isinstance(environment_id, str) else ""
        if not session_id and not new_environment_id:
            raise InvalidActionParametersException(
                "environmentId is required when starting a new session"
            )
        raw_vault_name = props.get("vaultName")
        if raw_vault_name is None or raw_vault_name == "":
            vault_name = None
        elif not isinstance(raw_vault_name, str):
            raise InvalidActionParametersException("vaultName must be a string")
        else:
            vault_name = raw_vault_name.strip() or None

        await ocean.port_client.post_run_log(
            run,
            (
                f"Sending prompt to Claude agent {agent_id} " f"(session {session_id})"
                if session_id
                else f"Starting a new session for Claude agent {agent_id}"
            ),
            status_label=STARTING_STATUS_LABEL,
            should_raise=False,
        )

        uses_port_mcp = await agent_uses_port_mcp(self.client, agent_id)

        if session_id:
            session = await self._ensure_session_continuable(session_id)
            if uses_port_mcp:
                await refresh_port_mcp_session(self.client, run, session, vault_name)
        else:
            api_config = await normalize_session_config(config)
            if uses_port_mcp:
                api_config = await prepare_port_mcp_session_config(
                    self.client,
                    run,
                    new_environment_id,
                    api_config,
                    vault_name,
                )
            session = await self.client.create_session(
                agent_id,
                new_environment_id,
                extra=api_config or None,
            )
            if not session.id:
                raise ActionExecutionError(
                    "Session was created but no session id was returned",
                    status_label=SESSION_START_FAILED_STATUS_LABEL,
                )

        resolved_session_id = session.id
        user_message = await self.client.send_user_message(resolved_session_id, prompt)
        logger.info(
            f"Triggered Claude agent {agent_id} via session {resolved_session_id} "
            f"(message {user_message.id}) for run {run.id}"
        )

        report_session_status = props.get("reportSessionStatus", False)

        if report_session_status:
            await get_stream_manager().track(resolved_session_id, run)

        # Reflect the session in the catalog (no-op if the `session` kind is
        # not mapped). Status updates arrive later via webhooks. Best-effort:
        # never fails the run. Convert to dict only at the catalog boundary.
        await self.register_entity(
            ObjectKind.SESSION, session.to_dict(mode="json"), run
        )

        external_id = build_external_id(resolved_session_id, user_message.id)
        session_url = build_session_link(
            self.client.get_console_host(),
            self.client.get_workspace_id(),
            resolved_session_id,
        )
        await ocean.port_client.update_run_started(
            run,
            session_url,
            external_id,
            extra_output=TriggerAgentSessionOutput(
                session_id=resolved_session_id,
                user_message_event_id=user_message.id,
                url=session_url,
            ).model_dump(),
            status_label=SESSION_RUNNING_STATUS_LABEL,
        )

        if report_session_status:
            try:
                await self.client.update_session(
                    resolved_session_id,
                    metadata={"portExternalRunId": external_id},
                )
            except Exception as exc:
                logger.warning(
                    f"Failed to store portExternalRunId on session "
                    f"{resolved_session_id}: {exc!r}"
                )

        else:
            await ocean.port_client.report_run_completed(
                run,
                True,
                f"Prompt sent to session {resolved_session_id}",
                status_label=PROMPT_SENT_STATUS_LABEL,
            )
