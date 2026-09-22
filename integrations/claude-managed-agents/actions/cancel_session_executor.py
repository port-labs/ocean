from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun
from port_ocean.exceptions.execution_manager import ActionExecutionError

from actions.abstract_executor import AbstractAnthropicExecutor
from actions.exceptions import InvalidActionParametersException
from integration import ObjectKind

CANCELLING_STATUS_LABEL = "Cancelling session"
CANCEL_FAILED_STATUS_LABEL = "Cancel failed"
SESSION_CANCELLED_STATUS_LABEL = "Session cancelled"
SESSION_NOT_CANCELLABLE_STATUS_LABEL = "Cannot cancel"

# A session only has work to interrupt while it is running; the remaining
# statuses either never started or have already stopped.
CANCELLABLE_STATUS = "running"


class CancelSessionExecutor(AbstractAnthropicExecutor):
    """Executor for the `cancel_session` action.

    Interrupts a running Claude session, which pauses agent execution and
    returns control to the user. The interrupt is acknowledged synchronously,
    so the run completes here rather than waiting for a webhook.

    Runs are serialized per session id so two cancels cannot race on the same
    session.
    """

    ACTION_NAME = "cancel_session"

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        session_id = run.execution_properties.get("sessionId")
        if session_id:
            return session_id
        return None

    async def execute(self, run: IntegrationRun) -> None:
        props = run.execution_properties
        session_id = props.get("sessionId")
        if not session_id:
            raise InvalidActionParametersException("sessionId is required")

        session_thread_id = props.get("sessionThreadId")

        await ocean.port_client.post_run_log(
            run,
            f"Cancelling Claude session {session_id}",
            status_label=CANCELLING_STATUS_LABEL,
            should_raise=False,
        )

        session = await self.client.get_session(session_id)
        status = session.get("status")
        if status != CANCELLABLE_STATUS:
            raise ActionExecutionError(
                f"Session {session_id} cannot be cancelled (status={status!r}); "
                f"only {CANCELLABLE_STATUS} sessions can be interrupted",
                status_label=SESSION_NOT_CANCELLABLE_STATUS_LABEL,
            )

        try:
            interrupt = await self.client.send_user_interrupt(
                session_id, session_thread_id
            )
        except Exception as error:
            raise ActionExecutionError(
                f"Failed to cancel session {session_id}: {error}",
                status_label=CANCEL_FAILED_STATUS_LABEL,
            ) from error

        logger.info(
            f"Cancelled Claude session {session_id} "
            f"(interrupt {interrupt.id}) for run {run.id}"
        )

        # Reflect the session in the catalog (no-op if the `session` kind is
        # not mapped). Best-effort: never fails the run.
        await self.register_entity(ObjectKind.SESSION, session, run)

        if isinstance(run, WorkflowNodeRun):
            run.output["sessionId"] = session_id
            run.output["interruptEventId"] = interrupt.id

        await ocean.port_client.report_run_completed(
            run,
            True,
            f"Cancelled session {session_id}",
            status_label=SESSION_CANCELLED_STATUS_LABEL,
        )
