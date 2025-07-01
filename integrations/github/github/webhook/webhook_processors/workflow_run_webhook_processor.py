from loguru import logger
from github.core.exporters.workflow_runs_exporter import RestWorkflowRunExporter
from github.core.options import SingleWorkflowRunOptions
from github.webhook.events import WORKFLOW_DELETE_EVENTS, WORKFLOW_UPSERT_EVENTS
from github.helpers.utils import ObjectKind
from github.clients.client_factory import create_github_client
from github.webhook.webhook_processors.base_repository_webhook_processor import (
    BaseRepositoryWebhookProcessor,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


class WorkflowRunWebhookProcessor(BaseRepositoryWebhookProcessor):
    async def _should_process_event(self, event: WebhookEvent) -> bool:
        if event.payload.get("action") and event.payload["action"] not in (
            WORKFLOW_DELETE_EVENTS + WORKFLOW_UPSERT_EVENTS
        ):
            return False
        return event.headers.get("x-github-event") == "workflow_run"

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.WORKFLOW_RUN]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        action = payload["action"]
        repo = payload["repository"]
        workflow_run = payload["workflow_run"]

        logger.info(f"Processing workflow run event: {action}")

        if action in WORKFLOW_DELETE_EVENTS:
            logger.info(f"Workflow run {workflow_run['name']} was deleted")

            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[workflow_run]
            )
        exporter = RestWorkflowRunExporter(create_github_client())
        options = SingleWorkflowRunOptions(
            repo_name=repo["name"], run_id=workflow_run["id"]
        )

        data_to_upsert = await exporter.get_resource(options)
        logger.info(f"Workflow run {data_to_upsert['name']} was upserted")

        return WebhookEventRawResults(
            updated_raw_results=[data_to_upsert], deleted_raw_results=[]
        )

    async def _validate_payload(self, payload: EventPayload) -> bool:
        if not {"action", "workflow_run"} <= payload.keys():
            return False

        return bool(payload["workflow_run"].get("id"))
