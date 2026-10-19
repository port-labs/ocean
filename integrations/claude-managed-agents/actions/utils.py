from typing import Any, Literal

from anthropic.types.beta.sessions.beta_managed_agents_agent_message_event import (
    BetaManagedAgentsAgentMessageEvent,
)
from anthropic.types.beta.sessions.beta_managed_agents_session_error_event import (
    BetaManagedAgentsSessionErrorEvent,
)
from anthropic.types.beta.sessions.beta_managed_agents_session_event import (
    BetaManagedAgentsSessionEvent,
)
from anthropic.types.beta.sessions.beta_managed_agents_text_block import (
    BetaManagedAgentsTextBlock,
)
from port_ocean.context.ocean import ocean
from port_ocean.core.models import WorkflowNodeRun, WorkflowNodeRunLog
from port_ocean.exceptions.execution_manager import ActionExecutionError

EXTERNAL_ID_PREFIX = "claude_session"


def build_external_id(session_id: str, user_message_event_id: str) -> str:
    """Build the Port externalRunId used to correlate session webhooks to runs."""
    return f"{EXTERNAL_ID_PREFIX}_{session_id}_{user_message_event_id}"


def build_session_link(
    console_host: str, workspace_id: str | None, session_id: str
) -> str:
    """Build a best-effort console link to the session for run output.

    ``console_host`` is the configured `platformConsoleHost`, independent of
    the Anthropic API host. Falls back to the console root if the workspace id
    wasn't captured (e.g. the anthropic-workspace-id header was unexpectedly
    absent).
    """
    if not workspace_id:
        return f"{console_host}/"
    return f"{console_host}/workspaces/{workspace_id}/sessions/{session_id}"


def _inject_github_authorization_tokens(config: dict[str, Any]) -> None:
    resources = config.get("resources")
    if not isinstance(resources, list):
        return

    github_pat = ocean.integration_config.get("github_authorization_token")

    for resource in resources:
        if not isinstance(resource, dict):
            continue
        if resource.get("type") != "github_repository":
            continue
        if resource.get("authorization_token"):
            continue
        if not github_pat:
            raise ActionExecutionError(
                "github_authorization_token must be configured on the integration "
                "when attaching GitHub repositories without authorization_token"
            )
        resource["authorization_token"] = github_pat


async def normalize_session_config(config: dict[str, Any]) -> dict[str, Any]:
    """Prepare session create config for the Anthropic API.

    Injects GitHub authorization tokens into github_repository resources.
    MCP servers and vault credentials are declared in the workflow configuration.
    """
    working = dict(config)
    _inject_github_authorization_tokens(working)
    return working


def format_session_event(
    event: BetaManagedAgentsSessionEvent,
) -> WorkflowNodeRunLog | None:
    """Return a log entry for ``event``, or ``None`` if the event type is not logged.

    ``agent.message`` events become INFO lines; ``session.error`` events become
    WARN (retrying) or ERROR (exhausted).  All other event types are ignored.
    """
    if isinstance(event, BetaManagedAgentsAgentMessageEvent):
        text = "\n".join(
            block.text
            for block in event.content
            if isinstance(block, BetaManagedAgentsTextBlock)
        )
        if text:
            return WorkflowNodeRunLog(level="INFO", message=text)
    elif isinstance(event, BetaManagedAgentsSessionErrorEvent):
        level: Literal["WARN", "ERROR"] = (
            "WARN" if event.error.retry_status.type == "retrying" else "ERROR"
        )
        return WorkflowNodeRunLog(
            level=level,
            message=f"Session error ({event.error.type}): {event.error.message}",
        )
    return None


async def post_interaction_logs(
    run: WorkflowNodeRun,
    events: list[BetaManagedAgentsSessionEvent],
) -> None:
    """Format interaction events and post any resulting log lines to ``run``.

    Only ``agent.message`` and ``session.error`` events produce log lines.
    Best-effort: never raises.
    """
    logs = [log for event in events if (log := format_session_event(event)) is not None]
    if logs:
        await ocean.port_client.post_wf_node_run_logs(run.id, logs, should_raise=False)
