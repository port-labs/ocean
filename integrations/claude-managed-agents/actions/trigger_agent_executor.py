from typing import Any, Self

from anthropic.types.beta import BetaManagedAgentsAgent
from anthropic.types.beta.beta_managed_agents_session import BetaManagedAgentsSession
from anthropic.types.beta.sessions.beta_managed_agents_session_requires_action import (
    BetaManagedAgentsSessionRequiresAction,
)
from anthropic.types.beta.sessions.beta_managed_agents_session_status_idle_event import (
    BetaManagedAgentsSessionStatusIdleEvent,
)
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun
from port_ocean.exceptions.execution_manager import ActionExecutionError
from pydantic import Field, model_validator
from utils.cache import Cache
from actions.abstract_action_input import AbstractAnthropicActionInput
from actions.abstract_executor import AbstractAnthropicExecutor
from actions.port_mcp import (
    PortMcpBinding,
    ensure_port_mcp_binding,
    is_agent_configured_with_port_mcp,
    remint_port_mcp_credential,
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
PORT_IDENTITY_ID_KEY = "port_identity_id"

_CACHE_TTL_SECONDS = 120
_CACHE_MAX_ITEMS = 100


class TriggerAgentInputs(AbstractAnthropicActionInput):
    agentId: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    sessionId: str | None = None
    environmentId: str = ""
    vaultName: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    reportSessionStatus: bool = False

    @model_validator(mode="after")
    def require_environment_for_new_session(self) -> Self:
        if not self.sessionId and not self.environmentId:
            raise ValueError("environmentId is required when starting a new session")
        return self


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

    _agent_cache = Cache[BetaManagedAgentsAgent](
        ttl_seconds=_CACHE_TTL_SECONDS, max_items=_CACHE_MAX_ITEMS
    )
    _port_mcp_cache = Cache[PortMcpBinding](
        ttl_seconds=_CACHE_TTL_SECONDS, max_items=_CACHE_MAX_ITEMS
    )

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        session_id = run.execution_properties.get("sessionId")
        if session_id:
            return session_id
        return None

    async def _resolve_port_mcp_binding(
        self,
        run: WorkflowNodeRun,
        vault_name: str | None,
    ) -> PortMcpBinding:
        ensured_vault_name = (
            vault_name or f"port-mcp-{run.execution_identity.identifier}"
        )
        binding = self._port_mcp_cache.get(ensured_vault_name)
        if binding is None:
            binding = await ensure_port_mcp_binding(
                self.client, run, ensured_vault_name
            )
            self._port_mcp_cache.set(ensured_vault_name, binding)
        else:
            await remint_port_mcp_credential(self.client, run, binding)
        return binding

    async def _ensure_session_continuable(
        self, session_id: str, run: WorkflowNodeRun
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

        owner = (session.metadata or {}).get(PORT_IDENTITY_ID_KEY)
        if not owner:
            raise ActionExecutionError(
                f"Cannot continue session {session.id}: session wasn't created by Port"
            )
        if run.execution_identity is None:
            raise ActionExecutionError(
                f"Cannot continue session {session.id}: owned by {owner} "
                "without an execution identity"
            )
        if owner != run.execution_identity.identifier:
            raise ActionExecutionError(
                f"Cannot continue session {session.id}: owned by {owner}, "
                f"run is {run.execution_identity.identifier}"
            )

        return session

    async def execute(self, run: IntegrationRun) -> None:
        inputs = TriggerAgentInputs.from_execution_properties(run.execution_properties)

        await ocean.port_client.post_run_log(
            run,
            (
                f"Sending prompt to Claude agent {inputs.agentId} "
                f"(session {inputs.sessionId})"
                if inputs.sessionId
                else f"Starting a new session for Claude agent {inputs.agentId}"
            ),
            status_label=STARTING_STATUS_LABEL,
            should_raise=False,
        )

        agent = await self._agent_cache.get_or_fetch(
            inputs.agentId, lambda: self.client.get_agent(inputs.agentId)
        )
        should_authenticate_port_mcp = (
            is_agent_configured_with_port_mcp(agent.mcp_servers)
            and isinstance(run, WorkflowNodeRun)
            and run.execution_identity is not None
        )
        if inputs.sessionId:
            if not isinstance(run, WorkflowNodeRun):
                raise ActionExecutionError(
                    "Continuing a session requires a workflow node run"
                )
            session = await self._ensure_session_continuable(inputs.sessionId, run)
            if should_authenticate_port_mcp:
                await self._resolve_port_mcp_binding(run, inputs.vaultName)
        else:
            api_config = await normalize_session_config(inputs.config)
            if should_authenticate_port_mcp:
                binding = await self._resolve_port_mcp_binding(run, inputs.vaultName)
                vault_ids = list(api_config.get("vault_ids") or [])
                if binding.vault_id not in vault_ids:
                    vault_ids.append(binding.vault_id)
                api_config = {
                    **api_config,
                    "metadata": {
                        **(api_config.get("metadata") or {}),
                        PORT_IDENTITY_ID_KEY: run.execution_identity.identifier,
                    },
                    "vault_ids": vault_ids,
                }
            session = await self.client.create_session(
                inputs.agentId,
                inputs.environmentId,
                extra=api_config or None,
            )
            if not session.id:
                raise ActionExecutionError(
                    "Session was created but no session id was returned",
                    status_label=SESSION_START_FAILED_STATUS_LABEL,
                )

        user_message = await self.client.send_user_message(session.id, inputs.prompt)
        logger.info(
            f"Triggered Claude agent {inputs.agentId} via session {session.id} "
            f"(message {user_message.id}) for run {run.id}"
        )

        # Reflect the session in the catalog (no-op if the `session` kind is
        # not mapped). Status updates arrive later via webhooks. Best-effort:
        # never fails the run. Convert to dict only at the catalog boundary.
        await self.register_entity(
            ObjectKind.SESSION, session.to_dict(mode="json"), run
        )

        external_id = build_external_id(session.id, user_message.id)
        session_url = build_session_link(
            self.client.get_console_host(),
            self.client.get_workspace_id(),
            session.id,
        )
        await ocean.port_client.update_run_started(
            run,
            session_url,
            external_id,
            extra_output=TriggerAgentSessionOutput(
                session_id=session.id,
                user_message_event_id=user_message.id,
                url=session_url,
            ).model_dump(),
            status_label=SESSION_RUNNING_STATUS_LABEL,
        )

        if inputs.reportSessionStatus:
            try:
                await self.client.update_session(
                    session.id,
                    metadata={"portExternalRunId": external_id},
                )
                await get_stream_manager().track(session.id, run)
            except Exception as exc:
                logger.warning(
                    f"Failed to store portExternalRunId on session "
                    f"{session.id}: {exc!r}"
                )
            return

        await ocean.port_client.report_run_completed(
            run,
            True,
            f"Prompt sent to session {session.id}",
            status_label=PROMPT_SENT_STATUS_LABEL,
        )
