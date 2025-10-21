from abc import abstractmethod
from github.webhook.events import WORKFLOW_DELETE_EVENTS, WORKFLOW_UPSERT_EVENTS
from github.helpers.utils import ObjectKind
from github.webhook.webhook_processors.base_repository_webhook_processor import (
    BaseRepositoryWebhookProcessor,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


class BaseWorkflowRunWebhookProcessor(BaseRepositoryWebhookProcessor):
    async def _should_process_event(self, event: WebhookEvent) -> bool:
        if event.payload.get("action") and event.payload["action"] not in (
            WORKFLOW_DELETE_EVENTS + WORKFLOW_UPSERT_EVENTS
        ):
            return False
        return event.headers.get("x-github-event") == "workflow_run"

    async def _validate_payload(self, payload: EventPayload) -> bool:
        if not {"action", "workflow_run"} <= payload.keys():
            return False

        return bool(payload["workflow_run"].get("id"))

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.WORKFLOW_RUN]

    @abstractmethod
    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        pass
