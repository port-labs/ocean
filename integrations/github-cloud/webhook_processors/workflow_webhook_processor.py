from typing import Any, Dict, cast
from loguru import logger
from initialize_client import get_client
from integration import ObjectKind, WorkflowResourceConfig
from port_ocean.core.handlers.port_app_config.models import ResourceConfig

from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)

from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEventRawResults,
    WebhookEvent,
    EventPayload,
    EventHeaders,
)


class WorkflowWebhookProcessor(AbstractWebhookProcessor):
    """Processor for GitHub workflow webhooks."""

    ACTIONS = [
        "created",
        "deleted",
        "updated",
        "disabled",
        "enabled",
    ]

    async def should_process_event(self, event: WebhookEvent) -> bool:
        """Check if the event should be processed by this handler."""
        return (
            event.headers.get("x-github-event") == "workflow_run"
            and event.payload.get("action") in self.ACTIONS
        )

    async def get_matching_kinds(self) -> list[str]:
        """Get the kinds of events this processor handles."""
        return [ObjectKind.WORKFLOW]

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate the webhook payload."""
        return bool(payload.get("workflow") and payload.get("repository"))

    async def handle_event(
        self, event: WebhookEvent, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Handle the workflow webhook event."""
        client = get_client()
        workflow = event["workflow"]
        repository = event["repository"]
        config = cast(WorkflowResourceConfig, resource_config)

        # Check if the repository's organization is in the configured organizations
        if repository["owner"]["login"] not in config.selector.organizations:
            logger.info(
                f"Skipping workflow {workflow['name']} from organization {repository['owner']['login']} not in configured organizations"
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        if event["action"] == "deleted":
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[workflow],
            )

        updated_workflow = await client.get_single_resource(
            resource_type="actions/workflows",
            owner=repository["owner"]["login"],
            repo=repository["name"],
            identifier=workflow["id"],
        )

        # Check if the workflow state matches the configured state
        if (
            config.selector.state != "all"
            and updated_workflow["state"] != config.selector.state
        ):
            logger.info(
                f"Skipping workflow {workflow['name']} with state {updated_workflow['state']} not matching configured state {config.selector.state}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        return WebhookEventRawResults(
            updated_raw_results=[updated_workflow],
            deleted_raw_results=[],
        )
