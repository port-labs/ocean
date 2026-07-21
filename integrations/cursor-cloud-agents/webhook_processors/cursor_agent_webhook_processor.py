from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    WebhookProcessorType,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.models import WorkflowNodeRun
from port_ocean.context.ocean import ocean

from core.catalog import (
    fetch_run_raw_for_catalog,
    try_upsert_entity,
)
from integration import ObjectKind
from clients.client_factory import create_cursor_agents_client
from webhook_processors.abstract_webhook_processor import (
    AbstractCursorWebhookProcessor,
)
from webhook_processors.utils import (
    parse_webhook_timestamp,
    resolve_cursor_run_id_for_webhook,
    resolve_tracked_run,
)

# v0 webhook `status` values, mirroring `apps/workflow-service/.../postCursorCallback.ts`.
# `CANCELLED` and `EXPIRED` are included defensively for blueprint parity even though
# v0 webhooks today only emit `FINISHED` and `ERROR`.
_TERMINAL_STATUSES = {"FINISHED", "ERROR", "CANCELLED", "EXPIRED"}


class CursorAgentWebhookProcessor(AbstractCursorWebhookProcessor):
    """Concludes `create_agent`/`trigger_agent` runs from v0 agent status webhooks.

    Cursor's v0 webhook payload carries agent snapshot fields (`status`,
    `summary`, `target`), which are written to the Port workflow run output.
    The same payload best-effort upserts ``cursor_agent`` and ``cursor_run``
    catalog entities (v0 fields normalized to the v1 mapping shape).

    The callback URL embeds the create Port run id for HMAC verification only.
    Port run correlation resolves the Cursor run id from the first page of List
    Runs (newest first) at or before the webhook timestamp, then looks up the
    in-progress Port run by Cursor run id (``trigger_agent``) or agent id
    (``create_agent``). When no in-progress run is found (for example after a
    v0 create with ``reportCompletion`` but a follow-up trigger without it),
    catalog entities are still upserted without calling ``report_run_completed``.
    """

    @classmethod
    def get_processor_type(cls) -> WebhookProcessorType:
        return WebhookProcessorType.ACTION

    async def should_process_event(self, event: WebhookEvent) -> bool:
        status = event.payload.get("status")
        return isinstance(status, str) and status in _TERMINAL_STATUSES

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return []

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig | None
    ) -> WebhookEventRawResults:
        agent_id = str(payload.get("id"))
        status = payload.get("status")

        webhook_time = parse_webhook_timestamp(payload)
        cursor_run_id = await resolve_cursor_run_id_for_webhook(agent_id, webhook_time)
        run = await resolve_tracked_run(agent_id, cursor_run_id)
        success = status == "FINISHED"
        summary = payload.get("summary")

        if run is None:
            logger.info(
                f"No in-progress run tracked for Cursor agent {agent_id} "
                f"(resolved Cursor run id={cursor_run_id}); "
                f"webhook status {status} - upserting catalog entities only"
            )
        elif isinstance(run, WorkflowNodeRun):
            output_update: dict[str, object] = {
                "status": status,
                "summary": summary,
                "target": payload.get("target"),
            }
            if cursor_run_id is not None:
                output_update["runId"] = cursor_run_id
            run.output.update(output_update)

        client = create_cursor_agents_client()
        console_host = client.get_console_host()
        await try_upsert_entity(
            ObjectKind.AGENT, dict(payload), console_host=console_host
        )
        if cursor_run_id is not None and isinstance(status, str):
            run_raw = await fetch_run_raw_for_catalog(
                client,
                agent_id,
                cursor_run_id,
                status=status,
                updated_at=webhook_time,
            )
            await try_upsert_entity(ObjectKind.RUN, run_raw)

        if run is not None:
            logger.info(
                f"Reporting run {run.id} as {'success' if success else 'failure'} "
                f"from Cursor agent {agent_id} webhook (status={status}, "
                f"cursorRunId={cursor_run_id})",
                run_id=run.id,
                agent_id=agent_id,
                cursor_run_id=cursor_run_id,
            )
            await ocean.port_client.report_run_completed(
                run,
                success,
                summary or f"Cursor agent {agent_id} finished with status {status}",
            )

        return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])
