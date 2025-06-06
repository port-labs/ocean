from loguru import logger
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
from github.core.options import SingleBranchOptions
from github.core.exporters.branch_exporter import RestBranchExporter


class BranchWebhookProcessor(BaseRepositoryWebhookProcessor):
    _event_type: str | None = None
    _allowed_branch_events = ["create", "delete", "push"]

    async def _validate_payload(self, payload: EventPayload) -> bool:
        return "ref" in payload

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        event_type = event.headers.get("x-github-event")
        if event_type not in self._allowed_branch_events:
            return False

        self._event_type = event_type
        if event_type == "push":
            return event.payload.get("ref", "").startswith("refs/heads/")

        return event.payload.get("ref_type") == "branch"

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.BRANCH]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        ref = payload["ref"]
        repo = payload["repository"]
        branch_name = ref.replace("refs/heads/", "")
        repo_name = repo["name"]

        logger.info(
            f"Processing branch event: {self._event_type} for branch {branch_name} in {repo_name}"
        )

        if self._event_type == "delete":
            data_to_delete = {"name": branch_name}
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[data_to_delete]
            )

        rest_client = create_github_client()
        exporter = RestBranchExporter(rest_client)

        data_to_upsert = await exporter.get_resource(
            SingleBranchOptions(repo_name=repo_name, branch_name=branch_name)
        )

        return WebhookEventRawResults(
            updated_raw_results=[data_to_upsert], deleted_raw_results=[]
        )
