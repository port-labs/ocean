from datetime import datetime
from typing import Any, Literal

from anthropic.types.beta import (
    BetaWebhookSessionIdledEventData,
    BetaWebhookSessionStatusIdledEventData,
    UnwrapWebhookEvent,
)
from anthropic.types.beta.sessions.beta_managed_agents_agent_message_event import (
    BetaManagedAgentsAgentMessageEvent,
)
from anthropic.types.beta.sessions.beta_managed_agents_session_error_event import (
    BetaManagedAgentsSessionErrorEvent,
)
from anthropic.types.beta.sessions.beta_managed_agents_session_event import (
    BetaManagedAgentsSessionEvent,
)
from anthropic.types.beta.sessions.beta_managed_agents_session_status_idle_event import (
    BetaManagedAgentsSessionStatusIdleEvent,
)
from anthropic.types.beta.sessions.beta_managed_agents_text_block import (
    BetaManagedAgentsTextBlock,
)
from anthropic.types.beta.sessions.beta_managed_agents_user_message_event import (
    BetaManagedAgentsUserMessageEvent,
)
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    WebhookProcessorType,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.models import (
    ActionRun,
    WorkflowNodeRun,
    WorkflowNodeRunLog,
    WorkflowNodeRunResult,
    WorkflowNodeRunStatus,
)

from actions.utils import build_external_id
from clients.client_factory import create_anthropic_client
from webhook_processors.abstract_webhook_processor import (
    AbstractAnthropicWebhookProcessor,
)

LogLevel = Literal["INFO", "WARNING", "ERROR", "DEBUG"]
WfLogLevel = Literal["INFO", "WARN", "ERROR", "DEBUG"]

# The workflow node logs API expects "WARN" where the action API uses "WARNING".
_WF_LOG_LEVEL: dict[LogLevel, WfLogLevel] = {
    "INFO": "INFO",
    "WARNING": "WARN",
    "ERROR": "ERROR",
    "DEBUG": "DEBUG",
}

SESSION_SUCCESS_WEBHOOK_DATA = (
    BetaWebhookSessionIdledEventData,
    BetaWebhookSessionStatusIdledEventData,
)

_INTERACTION_EVENT_TYPES = ["session.error", "session.status_idle", "agent.message"]

_TERMINAL_SESSION_WEBHOOK_TYPES = {
    "session.idled",
    "session.status_idled",
    "session.status_terminated",
}


class TriggerAgentWebhookProcessor(AbstractAnthropicWebhookProcessor):
    """Reports `trigger_agent` node-run status from session webhooks.

    Session webhooks are thin status pings. When a session reaches a terminal
    state, the matching Port run (correlated by external id) is completed with
    success or failure. Session errors for the interaction are written to the
    run logs; live conversation streaming is out of scope for v1.
    """

    @staticmethod
    def _session_error_log_level(
        error_event: BetaManagedAgentsSessionErrorEvent,
    ) -> LogLevel:
        """Transient errors the server is still retrying are warnings, not hard failures."""
        if error_event.error.retry_status.type == "retrying":
            return "WARNING"
        return "ERROR"

    @staticmethod
    def _format_session_error(
        error_event: BetaManagedAgentsSessionErrorEvent,
    ) -> tuple[LogLevel, str]:
        level = TriggerAgentWebhookProcessor._session_error_log_level(error_event)
        return (
            level,
            f"Session error ({error_event.error.type}): {error_event.error.message}",
        )

    @staticmethod
    def _is_failure_event(event: BetaManagedAgentsSessionEvent) -> bool:
        """Whether the session idle ``stop_reason`` marks the interaction as failed."""
        if isinstance(event, BetaManagedAgentsSessionStatusIdleEvent):
            return event.stop_reason.type == "retries_exhausted"
        return False

    @staticmethod
    def _last_error_log_message(entries: list[tuple[LogLevel, str]]) -> str | None:
        last_error: str | None = None
        for level, message in entries:
            if level == "ERROR":
                last_error = message
        return last_error

    @staticmethod
    def _extract_agent_message_text(event: BetaManagedAgentsAgentMessageEvent) -> str:
        parts: list[str] = []
        for block in event.content:
            if isinstance(block, BetaManagedAgentsTextBlock):
                parts.append(block.text)
        return "\n".join(parts)

    @staticmethod
    async def _complete_port_run(
        run: ActionRun | WorkflowNodeRun,
        success: bool,
        *,
        extra_output: dict[str, str] | None = None,
    ) -> None:
        """Complete a Port run, merging ``extra_output`` into workflow node output when set."""
        if isinstance(run, WorkflowNodeRun) and extra_output is not None:
            existing_output: dict[str, Any] = run.output
            await ocean.port_client.patch_wf_node_run(
                run.id,
                {
                    "status": WorkflowNodeRunStatus.COMPLETED,
                    "result": (
                        WorkflowNodeRunResult.SUCCESS
                        if success
                        else WorkflowNodeRunResult.FAILED
                    ),
                    "output": {**existing_output, **extra_output},
                },
            )
            return

        await ocean.port_client.report_run_completed(run, success)

    @classmethod
    def get_processor_type(cls) -> WebhookProcessorType:
        return WebhookProcessorType.ACTION

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return self.get_event_type(event.payload) in _TERMINAL_SESSION_WEBHOOK_TYPES

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return []

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig | None
    ) -> WebhookEventRawResults:
        webhook_event = UnwrapWebhookEvent.model_validate(payload)
        webhook_time = webhook_event.created_at
        data = webhook_event.data
        session_id = data.id

        anchor = await self._find_anchor_user_message(session_id, webhook_time)
        if anchor is None:
            logger.warning(
                f"No user message found before webhook time for session {session_id}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        external_id = build_external_id(session_id, anchor.id)
        run = await ocean.port_client.find_run_by_external_id(external_id)
        if not (
            run
            and ocean.port_client.is_run_in_progress(run)
            and run.execution_properties.get("reportSessionStatus", False)
        ):
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        if run.execution_properties.get("sessionId"):
            idle_search_before = (
                anchor.processed_at
                if isinstance(anchor.processed_at, datetime)
                else webhook_time
            )
            prior_idle_time = await self._find_prior_idle_time(
                session_id, idle_search_before
            )
        else:
            # A freshly created session
            prior_idle_time = None

        events = await self._fetch_interaction_events(
            session_id, prior_idle_time, webhook_time
        )
        interaction_failed, log_entries = self._detect_failure_and_log_entries(events)
        await self._post_run_logs(run, log_entries)
        last_error = self._last_error_log_message(log_entries)

        webhook_succeeded = isinstance(data, SESSION_SUCCESS_WEBHOOK_DATA)
        success = webhook_succeeded and not interaction_failed

        extra_output: dict[str, str] = {}
        if success:
            response = self._extract_last_agent_response(
                events,
                prior_idle_time=prior_idle_time,
                anchor_processed_at=anchor.processed_at,
            )
            if response is not None:
                extra_output["response"] = response
        elif not success and last_error is not None:
            extra_output["error"] = last_error

        logger.info(
            f"Reporting run {run.id} as {'success' if success else 'failure'} "
            f"from session webhook {data.type}",
            run_id=run.id,
            session_id=session_id,
        )
        if extra_output:
            await self._complete_port_run(run, success, extra_output=extra_output)
        else:
            await self._complete_port_run(run, success)

        return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

    async def _find_anchor_user_message(
        self, session_id: str, webhook_time: datetime
    ) -> BetaManagedAgentsUserMessageEvent | None:
        client = create_anthropic_client()
        async for batch in client.get_session_events(
            session_id,
            types=["user.message"],
            order="desc",
            created_at_lt=webhook_time,
            limit=1,
        ):
            event = batch[0]
            if isinstance(event, BetaManagedAgentsUserMessageEvent):
                return event
            logger.warning(
                f"Expected user.message anchor for session {session_id}, got {event.type}"
            )
            return None
        return None

    async def _find_prior_idle_time(
        self, session_id: str, before: datetime
    ) -> datetime | None:
        """Return ``processed_at`` of the last idle event strictly before ``before``."""
        client = create_anthropic_client()
        async for batch in client.get_session_events(
            session_id,
            types=["session.status_idle"],
            order="desc",
            created_at_lt=before,
            limit=1,
        ):
            event = batch[0]
            if not isinstance(event, BetaManagedAgentsSessionStatusIdleEvent):
                logger.warning(
                    f"Expected session.status_idle for session {session_id}, "
                    f"got {event.type}"
                )
                return None
            processed_at = event.processed_at
            if isinstance(processed_at, datetime):
                return processed_at
            logger.warning(
                f"session.status_idle for session {session_id} has no processed_at"
            )
            return None
        return None

    async def _fetch_interaction_events(
        self,
        session_id: str,
        prior_idle_time: datetime | None,
        webhook_time: datetime,
    ) -> list[BetaManagedAgentsSessionEvent]:
        """Fetch this interaction's errors, idle transitions, and agent messages.

        When a prior ``session.status_idle`` exists, events are scoped with
        ``created_at_gt`` from that idle through ``webhook_time``. On a new
        session with no prior idle, no lower bound is applied. Best-effort: on
        fetch error, an empty list is returned and the run still completes
        without logs or a response.
        """
        list_kwargs: dict[str, Any] = {
            "types": _INTERACTION_EVENT_TYPES,
            "created_at_lte": webhook_time,
            "order": "asc",
        }
        if prior_idle_time is not None:
            list_kwargs["created_at_gt"] = prior_idle_time
        events: list[BetaManagedAgentsSessionEvent] = []
        try:
            client = create_anthropic_client()
            async for batch in client.get_session_events(session_id, **list_kwargs):
                events.extend(batch)
        except Exception as error:
            logger.warning(
                f"Failed to inspect session events for {session_id} "
                f"(completing run anyway): {error}"
            )
            return []
        return events

    def _detect_failure_and_log_entries(
        self, events: list[BetaManagedAgentsSessionEvent]
    ) -> tuple[bool, list[tuple[LogLevel, str]]]:
        """Detect interaction failure and collect session error log entries.

        Success/failure uses only the idle event ``stop_reason`` (via
        ``_is_failure_event``); ``session.error`` is logged but does not
        change the result.
        """
        failed = False
        log_entries: list[tuple[LogLevel, str]] = []
        for event in events:
            if isinstance(event, BetaManagedAgentsSessionErrorEvent):
                log_entries.append(self._format_session_error(event))
            failed = failed or self._is_failure_event(event)
        return failed, log_entries

    def _extract_last_agent_response(
        self,
        events: list[BetaManagedAgentsSessionEvent],
        *,
        prior_idle_time: datetime | None,
        anchor_processed_at: datetime | None,
    ) -> str | None:
        """Return the last agent message text scoped to this interaction.

        Mirrors the fetch's lower bound: events after ``prior_idle_time`` when
        available, otherwise events at or after ``anchor_processed_at`` (the
        combined fetch has no lower bound in that case, so filtering here
        excludes any earlier interaction's agent messages).
        """
        last_response: str | None = None
        for event in events:
            if not isinstance(event, BetaManagedAgentsAgentMessageEvent):
                continue
            if prior_idle_time is None and isinstance(anchor_processed_at, datetime):
                processed_at = event.processed_at
                if not (
                    isinstance(processed_at, datetime)
                    and processed_at >= anchor_processed_at
                ):
                    continue
            text = self._extract_agent_message_text(event)
            if text:
                last_response = text
        return last_response

    @staticmethod
    async def _post_run_logs(
        run: ActionRun | WorkflowNodeRun, entries: list[tuple[LogLevel, str]]
    ) -> None:
        """Write a batch of log lines to the run, in a single request when possible."""
        if not entries:
            return
        if isinstance(run, WorkflowNodeRun):
            logs = [
                WorkflowNodeRunLog(level=_WF_LOG_LEVEL[level], message=message)
                for level, message in entries
            ]
            await ocean.port_client.post_wf_node_run_logs(run.id, logs)
        else:
            for level, message in entries:
                await ocean.port_client.post_run_log(run, message, level=level)
