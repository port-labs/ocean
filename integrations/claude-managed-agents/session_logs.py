from typing import Literal

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


class SessionLogFormatter:
    """Formats Anthropic session events into Port workflow node run log entries.

    Only ``agent.message`` and ``session.error`` events produce log lines; all
    other event types are silently ignored.
    """

    @staticmethod
    def _agent_message_text(event: BetaManagedAgentsAgentMessageEvent) -> str:
        parts: list[str] = []
        for block in event.content:
            if isinstance(block, BetaManagedAgentsTextBlock):
                parts.append(block.text)
        return "\n".join(parts)

    @staticmethod
    def _format_error(
        event: BetaManagedAgentsSessionErrorEvent,
    ) -> WorkflowNodeRunLog:
        level: Literal["WARN", "ERROR"] = (
            "WARN" if event.error.retry_status.type == "retrying" else "ERROR"
        )
        return WorkflowNodeRunLog(
            level=level,
            message=f"Session error ({event.error.type}): {event.error.message}",
        )

    def format_event(
        self, event: BetaManagedAgentsSessionEvent
    ) -> WorkflowNodeRunLog | None:
        """Return a log entry for ``event``, or ``None`` if the event type is not logged."""
        if isinstance(event, BetaManagedAgentsAgentMessageEvent):
            text = self._agent_message_text(event)
            if text:
                return WorkflowNodeRunLog(level="INFO", message=text)
        elif isinstance(event, BetaManagedAgentsSessionErrorEvent):
            return self._format_error(event)
        return None

    def format_events(
        self, events: list[BetaManagedAgentsSessionEvent]
    ) -> list[WorkflowNodeRunLog]:
        """Return log entries for all events that produce a log line."""
        return [
            log for event in events if (log := self.format_event(event)) is not None
        ]


class InteractionLogReconciler:
    """Posts session event logs to a workflow node run.

    Called from the terminal session webhook with the interaction's pre-fetched
    events.  Formats ``agent.message`` and ``session.error`` events into log
    lines and posts them in one batch.

    Phase 1 (streaming) will extend this with a cursor store so the reconciler
    can skip events already posted by the live stream.
    """

    def __init__(self) -> None:
        self._formatter = SessionLogFormatter()

    async def post_logs_from_events(
        self,
        run: WorkflowNodeRun,
        events: list[BetaManagedAgentsSessionEvent],
    ) -> None:
        """Format ``events`` and post any resulting log lines to ``run``.

        Best-effort: never raises.
        """
        logs = self._formatter.format_events(events)
        if logs:
            await ocean.port_client.post_wf_node_run_logs(
                run.id, logs, should_raise=False
            )
