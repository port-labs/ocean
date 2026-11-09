from dataclasses import dataclass
from typing import Any, Self

from anthropic import APIStatusError
from anthropic.types.beta import BetaManagedAgentsAgent
from anthropic.types.beta.beta_managed_agents_session import BetaManagedAgentsSession
from anthropic.types.beta.sessions.beta_managed_agents_user_message_event import (
    BetaManagedAgentsUserMessageEvent,
)
from anthropic.types.beta.sessions.beta_managed_agents_session_requires_action import (
    BetaManagedAgentsSessionRequiresAction,
)
from anthropic.types.beta.sessions.beta_managed_agents_session_status_idle_event import (
    BetaManagedAgentsSessionStatusIdleEvent,
)
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import (
    IntegrationRun,
    ResolvedExecutionIdentity,
    WorkflowNodeRun,
)
from port_ocean.exceptions.execution_manager import ActionExecutionError
from pydantic import Field, model_validator
from port_ocean.utils.ttl_cache import TTLCache
from claude_managed_agents.actions.abstract_action_input import (
    AbstractAnthropicActionInput,
)
from claude_managed_agents.actions.abstract_executor import AbstractAnthropicExecutor
from claude_managed_agents.actions.port_mcp_utils import (
    PortMcpBinding,
    attach_port_mcp_settings_to_agent_config,
    ensure_port_mcp_credential,
    get_or_create_mcp_vault,
    port_family_mcp_urls_on_agent,
    port_mcp_binding_cache_key,
    remint_port_mcp_credential,
)
from claude_managed_agents.actions.prompt_images import (
    load_prompt_images,
    prompt_without_images,
)
from claude_managed_agents.actions.types import TriggerAgentSessionOutput
from claude_managed_agents.actions.utils import (
    build_external_id,
    build_session_link,
    normalize_session_config,
)
from claude_managed_agents.integration import ObjectKind
from claude_managed_agents.stream_manager import get_stream_manager
from claude_managed_agents.webhook_processors.registry import WEBHOOK_PATH
from claude_managed_agents.webhook_processors.trigger_agent_webhook_processor import (
    TriggerAgentWebhookProcessor,
)

STARTING_STATUS_LABEL = "Sending prompt"
SESSION_RUNNING_STATUS_LABEL = "Session running"
PROMPT_SENT_STATUS_LABEL = "Prompt sent"
SESSION_NOT_CONTINUABLE_STATUS_LABEL = "Cannot continue"
SESSION_START_FAILED_STATUS_LABEL = "Start failed"
PORT_IDENTITY_ID_KEY = "port_identity_id"

# Claude refuses an image by its size or dimensions with a 400, and a request that is too large with a 413.
IMAGES_REJECTED_STATUS = (400, 413)
MAX_LISTED_IMAGES = 10
_CACHE_TTL_SECONDS = 120
_CACHE_MAX_ITEMS = 100


class TriggerAgentInputs(AbstractAnthropicActionInput):
    agentId: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    sessionId: str | None = None
    environmentId: str = ""
    vaultName: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    enablePortMcp: bool = True
    virtualMcpServerIds: list[str] = Field(default_factory=list)
    reportSessionStatus: bool = False
    gitAccessToken: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def require_environment_for_new_session(self) -> Self:
        if not self.sessionId and not self.environmentId:
            raise ValueError("environmentId is required when starting a new session")
        return self


@dataclass(frozen=True)
class PortMcpWorkflowContext:
    workflow_run: WorkflowNodeRun
    execution_identity: ResolvedExecutionIdentity
    vault_name: str | None
    enable_port_mcp: bool
    virtual_mcp_server_ids: list[str]


def port_mcp_workflow_context(
    inputs: TriggerAgentInputs,
    run: IntegrationRun,
    agent: BetaManagedAgentsAgent | None = None,
) -> PortMcpWorkflowContext | None:
    """Return vault context when this run should ensure and/or remint Port-family MCPs.

    Input flags drive ensure/merge onto the agent. Remint targets come from the
    agent after ensure (including Port/virtual already present when inputs omit them).
    """
    if not isinstance(run, WorkflowNodeRun) or run.execution_identity is None:
        return None
    identity = run.execution_identity
    has_input = inputs.enablePortMcp or bool(inputs.virtualMcpServerIds)
    has_existing = bool(
        agent is not None and port_family_mcp_urls_on_agent(agent.mcp_servers or [])
    )
    if not has_input and not has_existing:
        return None
    return PortMcpWorkflowContext(
        run,
        identity,
        inputs.vaultName,
        inputs.enablePortMcp,
        inputs.virtualMcpServerIds,
    )


def session_config_with_port_mcp(
    api_config: dict[str, Any],
    vault_id: str,
    execution_identity: ResolvedExecutionIdentity,
) -> dict[str, Any]:
    vault_ids = list(api_config.get("vault_ids") or [])
    if vault_id not in vault_ids:
        vault_ids.append(vault_id)
    return {
        **api_config,
        "metadata": {
            **(api_config.get("metadata") or {}),
            PORT_IDENTITY_ID_KEY: execution_identity.identifier,
        },
        "vault_ids": vault_ids,
    }


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

    _agent_cache = TTLCache[BetaManagedAgentsAgent](
        ttl_seconds=_CACHE_TTL_SECONDS, max_items=_CACHE_MAX_ITEMS
    )
    _port_mcp_cache = TTLCache[PortMcpBinding](
        ttl_seconds=_CACHE_TTL_SECONDS, max_items=_CACHE_MAX_ITEMS
    )

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        session_id = run.execution_properties.get("sessionId")
        if session_id:
            return session_id
        return None

    async def _ensure_port_mcp_vault_ready(
        self,
        port_mcp: PortMcpWorkflowContext,
        agent: BetaManagedAgentsAgent,
    ) -> str:
        vault_name = port_mcp.vault_name or port_mcp.execution_identity.identifier
        mcp_urls = port_family_mcp_urls_on_agent(agent.mcp_servers or [])
        vault_id: str | None = None
        urls_to_resolve: set[str] = set(mcp_urls)

        for url in mcp_urls:
            cached = self._port_mcp_cache.get(
                port_mcp_binding_cache_key(vault_name, url)
            )
            if cached is None:
                continue
            vault_id = vault_id or cached.vault_id
            await remint_port_mcp_credential(self.client, port_mcp.workflow_run, cached)
            urls_to_resolve.discard(url)

        if vault_id is None:
            vault_id = (await get_or_create_mcp_vault(self.client, vault_name)).id

        for url in urls_to_resolve:
            binding = await ensure_port_mcp_credential(
                self.client,
                port_mcp.workflow_run,
                vault_id,
                url,
            )
            self._port_mcp_cache.set(
                port_mcp_binding_cache_key(vault_name, url), binding
            )

        return vault_id

    async def _ensure_session_continuable(
        self, session_id: str, run: IntegrationRun
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
        if owner:
            identity = (
                run.execution_identity if isinstance(run, WorkflowNodeRun) else None
            )
            if identity is None:
                raise ActionExecutionError(
                    f"Cannot continue session {session.id}: owned by {owner} "
                    "without an execution identity"
                )
            if owner != identity.identifier:
                raise ActionExecutionError(
                    f"Cannot continue session {session.id}: owned by {owner}, "
                    f"run is {identity.identifier}"
                )

        return session

    async def _ensure_agent_port_mcp_configured(
        self, agent: BetaManagedAgentsAgent, port_mcp: PortMcpWorkflowContext
    ) -> BetaManagedAgentsAgent:
        payload, changed = attach_port_mcp_settings_to_agent_config(
            {},
            existing_agent=agent,
            enable_port_mcp=port_mcp.enable_port_mcp,
            virtual_mcp_server_ids=port_mcp.virtual_mcp_server_ids,
        )
        if not changed:
            return agent
        updated = await self.client.update_agent(
            agent.id,
            version=agent.version,
            payload=payload,
        )
        self._agent_cache.set(agent.id, updated)
        return updated

    async def _create_new_trigger_session(
        self,
        inputs: TriggerAgentInputs,
        port_mcp: PortMcpWorkflowContext | None,
        agent: BetaManagedAgentsAgent,
    ) -> BetaManagedAgentsSession:
        api_config = await normalize_session_config(
            inputs.config,
            mount_token=inputs.gitAccessToken,
        )
        if port_mcp is not None:
            port_mcp_vault_id = await self._ensure_port_mcp_vault_ready(port_mcp, agent)
            api_config = session_config_with_port_mcp(
                api_config, port_mcp_vault_id, port_mcp.execution_identity
            )
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
        return session

    async def _send_prompt(
        self, session_id: str, prompt: str, run: IntegrationRun
    ) -> BetaManagedAgentsUserMessageEvent:
        """Sends the prompt with the Port images it links to. Images never fail the run.

        An image that can't be loaded is labeled "not attached" in the prompt and logged on the run. If Claude rejects
        the images themselves (a size or dimension it does not take), the prompt goes without any of them.
        """
        images = await load_prompt_images(prompt)
        if images.failed:
            await self._warn(
                run,
                f"Could not attach {len(images.failed)} image(s) linked in the prompt: "
                + ", ".join(images.failed[:MAX_LISTED_IMAGES])
                + (", ..." if len(images.failed) > MAX_LISTED_IMAGES else ""),
            )
        try:
            return await self.client.send_user_message(
                session_id, images.prompt, images.blocks
            )
        except APIStatusError as error:
            if not images.blocks or error.status_code not in IMAGES_REJECTED_STATUS:
                raise
            await self._warn(
                run,
                f"Claude rejected the images ({error.status_code}); sent the prompt without them",
            )
            return await self.client.send_user_message(
                session_id, prompt_without_images(prompt)
            )

    @staticmethod
    async def _warn(run: IntegrationRun, message: str) -> None:
        logger.warning(f"{message} (run {run.id})")
        await ocean.port_client.post_run_log(
            run, message, level="WARNING", should_raise=False
        )

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
        port_mcp = port_mcp_workflow_context(inputs, run, agent)
        if port_mcp is not None:
            agent = await self._ensure_agent_port_mcp_configured(agent, port_mcp)

        if inputs.sessionId:
            session = await self._ensure_session_continuable(inputs.sessionId, run)
            if port_mcp is not None:
                await self._ensure_port_mcp_vault_ready(port_mcp, agent)
        else:
            session = await self._create_new_trigger_session(inputs, port_mcp, agent)

        user_message = await self._send_prompt(session.id, inputs.prompt, run)
        logger.info(
            f"Triggered Claude agent {inputs.agentId} via session {session.id} "
            f"(message {user_message.id}) for run {run.id}"
        )

        # Reflect the session in the catalog (no-op if the `session` kind is
        # not mapped). Status updates arrive later via webhooks. Best-effort:
        # never fails the run. Convert to dict only at the catalog boundary.
        await self.register_entity(
            ObjectKind.SESSION, session.to_dict(mode="json", warnings=False), run
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
